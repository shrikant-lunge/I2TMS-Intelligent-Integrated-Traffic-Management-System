"""Adaptive signal timing pipeline for the I²TMS Flask app.

The implementation reuses the repository's Ultralytics YOLO dependency and
uses Ultralytics ByteTrack for video input. Image input is treated as a single
observation frame, so tracking IDs are not persisted across frames there.

The traffic metrics are prototype proxies with explicit assumptions:
- queue length is estimated from vehicles near the stop-line side of the frame
- occupancy is the ratio of total detection area to frame area
- average speed is pixel displacement per second, which is useful for relative
  comparison but not a physical km/h reading without camera calibration
- waiting time is estimated from track stationarity in video and from a small
  per-queued-vehicle proxy in a still image
"""

from __future__ import annotations

import logging
import math
import os
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.config import MIN_DETECTION_CONFIDENCE, YOLO_MODEL
from app.extensions import db
from app.models.adaptive_signal_state import AdaptiveSignalState
from app.models.junction import Junction
from app.models.settings import SystemSettings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrafficConstants:
    image_observation_window_sec: float = 15.0
    image_wait_seconds_per_queued_vehicle: float = 1.5
    saturation_flow_pcu_per_hr: float = 1800.0
    lost_time_sec: float = 12.0
    default_cycle_sec: float = 90.0
    min_green_sec: float = 15.0
    max_green_sec: float = 60.0
    queue_zone_ratio: float = 0.55
    stop_speed_px_per_sec: float = 6.0
    density_high: float = 0.65
    density_medium: float = 0.35
    queue_high: int = 18
    queue_medium: int = 8
    occupancy_high: float = 0.28
    occupancy_medium: float = 0.14
    waiting_high: float = 18.0
    waiting_medium: float = 8.0
    speed_low: float = 8.0
    speed_medium: float = 16.0


class AdaptiveSignalPipelineError(RuntimeError):
    pass


class ModelUnavailableError(AdaptiveSignalPipelineError):
    pass


class AdaptiveSignalPipeline:
    DIRECTIONS = ("north", "east", "south", "west")
    DIRECTION_LABELS = {
        "north": "NORTH",
        "east": "EAST",
        "south": "SOUTH",
        "west": "WEST",
    }
    ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
    ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov"}
    ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS

    NORMALIZED_CLASS_ALIASES = {
        "car": "car",
        "motorcycle": "bike",
        "bicycle": "bike",
        "bike": "bike",
        "scooty": "bike",
        "scooter": "bike",
        "rickshaw": "auto",
        "auto_rickshaw": "auto",
        "autorickshaw": "auto",
        "three_wheeler": "auto",
        "three-wheeler": "auto",
        "auto": "auto",
        "bus": "bus",
        "truck": "truck",
    }

    PCU_FACTORS = {
        "car": 1.0,
        "bike": 0.5,
        "auto": 0.8,
        "bus": 3.0,
        "truck": 3.0,
    }

    CONSTANTS = TrafficConstants()

    def __init__(self):
        self._model = None
        self._model_error: Optional[str] = None
        self._model_loaded = False
        self._model_lock = threading.RLock()

    def _load_model(self):
        with self._model_lock:
            if self._model_loaded:
                return self._model

            try:
                from ultralytics import YOLO

                model_path = str(YOLO_MODEL)
                self._model = YOLO(model_path)
                self._model_error = None
                self._model_loaded = True
                logger.info("Adaptive signal YOLO model loaded: %s", model_path)
                return self._model
            except Exception as exc:
                self._model_error = str(exc)
                self._model_loaded = True
                logger.exception("Unable to load YOLO model for adaptive signals")
                return None

    def _ensure_model(self):
        model = self._load_model()
        if model is None:
            raise ModelUnavailableError(self._model_error or "YOLO model unavailable")
        return model

    def _normalize_class_name(self, raw_class_name: str) -> Optional[str]:
        normalized = raw_class_name.strip().lower()
        return self.NORMALIZED_CLASS_ALIASES.get(normalized)

    def _supported_file_kind(self, file_name: str) -> Optional[str]:
        suffix = Path(file_name).suffix.lower()
        if suffix in self.ALLOWED_IMAGE_EXTENSIONS:
            return "image"
        if suffix in self.ALLOWED_VIDEO_EXTENSIONS:
            return "video"
        return None

    def validate_junction(self, junction_name: str) -> Junction:
        if not junction_name:
            raise ValueError("junction_name is required")

        junction = Junction.query.filter_by(name=junction_name).first()
        if junction:
            return junction

        if junction_name == "Rahate Colony Square":
            junction = Junction(name=junction_name, status="moderate", last_updated=datetime.utcnow())
            db.session.add(junction)
            db.session.commit()
            return junction

        raise LookupError(f"Junction not found: {junction_name}")

    def _get_system_limits(self) -> Tuple[float, float, float]:
        settings = SystemSettings.query.first()
        min_green = float(getattr(settings, "min_phase_duration_sec", self.CONSTANTS.min_green_sec))
        max_green = float(getattr(settings, "max_phase_duration_sec", self.CONSTANTS.max_green_sec))
        default_cycle = float(getattr(settings, "default_cycle_time_sec", self.CONSTANTS.default_cycle_sec))
        return min_green, max_green, default_cycle

    def _build_empty_state(self, junction_name: str, direction: str, source_kind: str) -> AdaptiveSignalState:
        return AdaptiveSignalState(
            junction_name=junction_name,
            direction=direction,
            vehicle_count_total=0,
            vehicle_count_by_class={"car": 0, "bus": 0, "auto": 0, "truck": 0, "bike": 0},
            queue_length=0,
            density=0.0,
            average_speed=0.0,
            occupancy=0.0,
            waiting_time=0.0,
            traffic_level="LOW",
            pcu_demand=0.0,
            demand_rate_pcu_per_hr=0.0,
            congestion_level="LOW",
            green_time_sec=0.0,
            source_kind=source_kind,
            updated_at=datetime.utcnow(),
        )

    def _ensure_direction_rows(self, junction_name: str, source_kind: str) -> Dict[str, AdaptiveSignalState]:
        states: Dict[str, AdaptiveSignalState] = {}
        for direction in self.DIRECTIONS:
            state = AdaptiveSignalState.query.filter_by(
                junction_name=junction_name,
                direction=direction,
            ).first()
            if state is None:
                state = self._build_empty_state(junction_name, direction, source_kind)
                db.session.add(state)
            states[direction] = state
        db.session.flush()
        return states

    def _detect_frame(self, frame: np.ndarray) -> List[dict]:
        model = self._ensure_model()
        with self._model_lock:
            results = model(frame, conf=MIN_DETECTION_CONFIDENCE, verbose=False)

        detections: List[dict] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            names = result.names or {}
            for box in boxes:
                cls_id = int(box.cls[0])
                raw_class = str(names.get(cls_id, cls_id)).strip().lower()
                normalized_class = self._normalize_class_name(raw_class)
                if normalized_class is None:
                    continue

                confidence = float(box.conf[0])
                x1, y1, x2, y2 = [int(value) for value in box.xyxy[0].tolist()]
                detections.append(
                    {
                        "class": normalized_class,
                        "confidence": round(confidence, 3),
                        "bbox": [x1, y1, x2, y2],
                        "raw_class": raw_class,
                    }
                )
        return detections

    def _track_frame(self, frame: np.ndarray) -> List[dict]:
        model = self._ensure_model()
        with self._model_lock:
            results = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=MIN_DETECTION_CONFIDENCE,
                verbose=False,
            )

        tracks: List[dict] = []
        for result in results:
            boxes = result.boxes
            if boxes is None or boxes.id is None:
                continue

            names = result.names or {}
            track_ids = boxes.id.tolist()
            for index, box in enumerate(boxes):
                cls_id = int(box.cls[0])
                raw_class = str(names.get(cls_id, cls_id)).strip().lower()
                normalized_class = self._normalize_class_name(raw_class)
                if normalized_class is None:
                    continue

                confidence = float(box.conf[0])
                x1, y1, x2, y2 = [int(value) for value in box.xyxy[0].tolist()]
                track_id = int(track_ids[index])
                tracks.append(
                    {
                        "track_id": track_id,
                        "class": normalized_class,
                        "confidence": round(confidence, 3),
                        "bbox": [x1, y1, x2, y2],
                        "raw_class": raw_class,
                        "center": [int((x1 + x2) / 2), int((y1 + y2) / 2)],
                    }
                )
        return tracks

    def calculate_pcu(self, vehicle_count_by_class: Dict[str, int]) -> Dict[str, object]:
        pcu_demand = 0.0
        for class_name, factor in self.PCU_FACTORS.items():
            pcu_demand += float(vehicle_count_by_class.get(class_name, 0)) * factor
        return {
            "pcu_factors": dict(self.PCU_FACTORS),
            "pcu_demand": round(pcu_demand, 2),
        }

    def estimate_congestion(self, pcu_demand: float, traffic_state: Dict[str, object]) -> Dict[str, object]:
        density = float(traffic_state.get("density", 0.0))
        queue_length = int(traffic_state.get("queue_length", 0))
        occupancy = float(traffic_state.get("occupancy", 0.0))
        average_speed = float(traffic_state.get("average_speed", 0.0))
        waiting_time = float(traffic_state.get("waiting_time", 0.0))
        vehicle_count = max(int(traffic_state.get("vehicle_count", 0)), 1)

        score = 0
        pcu_ratio = pcu_demand / vehicle_count

        if pcu_demand >= 30 or pcu_ratio >= 1.5:
            score += 2
        elif pcu_demand >= 16 or pcu_ratio >= 0.9:
            score += 1

        if density >= self.CONSTANTS.density_high:
            score += 2
        elif density >= self.CONSTANTS.density_medium:
            score += 1

        if queue_length >= self.CONSTANTS.queue_high:
            score += 2
        elif queue_length >= self.CONSTANTS.queue_medium:
            score += 1

        if occupancy >= self.CONSTANTS.occupancy_high:
            score += 1
        elif occupancy >= self.CONSTANTS.occupancy_medium:
            score += 1

        if waiting_time >= self.CONSTANTS.waiting_high:
            score += 2
        elif waiting_time >= self.CONSTANTS.waiting_medium:
            score += 1

        if average_speed <= self.CONSTANTS.speed_low:
            score += 2
        elif average_speed <= self.CONSTANTS.speed_medium:
            score += 1

        if score >= 6:
            level = "HIGH"
        elif score >= 3:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {
            "level": level,
            "score": score,
            "pcu_demand": round(float(pcu_demand), 2),
            "density": round(density, 3),
            "queue_length": queue_length,
        }

    def _traffic_level_from_state(
        self,
        queue_length: int,
        density: float,
        occupancy: float,
        average_speed: float,
        waiting_time: float,
    ) -> str:
        if (
            density >= self.CONSTANTS.density_high
            or queue_length >= self.CONSTANTS.queue_high
            or occupancy >= self.CONSTANTS.occupancy_high
            or waiting_time >= self.CONSTANTS.waiting_high
            or average_speed <= self.CONSTANTS.speed_low
        ):
            return "HIGH"
        if (
            density >= self.CONSTANTS.density_medium
            or queue_length >= self.CONSTANTS.queue_medium
            or occupancy >= self.CONSTANTS.occupancy_medium
            or waiting_time >= self.CONSTANTS.waiting_medium
            or average_speed <= self.CONSTANTS.speed_medium
        ):
            return "MEDIUM"
        return "LOW"

    def _estimate_traffic_state_from_detections(self, detections: List[dict], frame_shape: Tuple[int, int]) -> Dict[str, object]:
        height, width = frame_shape
        frame_area = float(max(height * width, 1))
        vehicle_count_by_class = {"car": 0, "bus": 0, "auto": 0, "truck": 0, "bike": 0}
        queue_length = 0
        total_bbox_area = 0.0

        for detection in detections:
            class_name = detection["class"]
            vehicle_count_by_class[class_name] += 1
            x1, y1, x2, y2 = detection["bbox"]
            bbox_area = max(0, x2 - x1) * max(0, y2 - y1)
            total_bbox_area += bbox_area
            center_y = (y1 + y2) / 2.0

            # Prototype queue proxy for a still image:
            # vehicles lower in the frame are assumed to be closer to the stop line.
            if center_y >= height * self.CONSTANTS.queue_zone_ratio:
                queue_length += 1

        vehicle_count = sum(vehicle_count_by_class.values())
        occupancy = min(1.0, total_bbox_area / frame_area)
        density = min(1.0, 0.65 * occupancy + 0.35 * (queue_length / max(vehicle_count, 1)))
        average_speed = 0.0
        waiting_time = round(queue_length * self.CONSTANTS.image_wait_seconds_per_queued_vehicle, 2)

        traffic_level = self._traffic_level_from_state(
            queue_length=queue_length,
            density=density,
            occupancy=occupancy,
            average_speed=average_speed,
            waiting_time=waiting_time,
        )

        return {
            "vehicle_count": vehicle_count,
            "vehicle_count_by_class": vehicle_count_by_class,
            "queue_length": queue_length,
            "density": round(density, 3),
            "average_speed": round(average_speed, 2),
            "occupancy": round(occupancy, 3),
            "waiting_time": round(waiting_time, 2),
            "traffic_level": traffic_level,
        }

    def _estimate_traffic_state_from_tracks(
        self,
        track_stats: Dict[int, dict],
        frame_shape: Tuple[int, int],
    ) -> Dict[str, object]:
        height, width = frame_shape
        frame_area = float(max(height * width, 1))
        vehicle_count_by_class = {"car": 0, "bus": 0, "auto": 0, "truck": 0, "bike": 0}
        queue_length = 0
        total_bbox_area = 0.0
        speed_samples: List[float] = []
        waiting_samples: List[float] = []

        for stats in track_stats.values():
            class_name = stats["class"]
            vehicle_count_by_class[class_name] += 1
            x1, y1, x2, y2 = stats["bbox"]
            total_bbox_area += max(0, x2 - x1) * max(0, y2 - y1)

            centroids: List[Tuple[int, int]] = stats["centroids"]
            frame_indices: List[int] = stats["frame_indices"]
            fps = max(float(stats["fps"]), 1.0)

            if len(centroids) >= 2:
                displacement = 0.0
                stationary_time = 0.0
                for index in range(1, len(centroids)):
                    prev_x, prev_y = centroids[index - 1]
                    curr_x, curr_y = centroids[index]
                    step = math.hypot(curr_x - prev_x, curr_y - prev_y)
                    displacement += step
                    if step <= self.CONSTANTS.stop_speed_px_per_sec / fps:
                        stationary_time += 1.0 / fps

                elapsed = max((frame_indices[-1] - frame_indices[0]) / fps, 1.0 / fps)
                speed_samples.append(displacement / elapsed)
                waiting_samples.append(stationary_time)
            else:
                speed_samples.append(0.0)
                waiting_samples.append(0.0)

            mean_y = sum(point[1] for point in centroids) / max(len(centroids), 1)
            latest_speed = speed_samples[-1] if speed_samples else 0.0
            if mean_y >= height * self.CONSTANTS.queue_zone_ratio and latest_speed <= self.CONSTANTS.stop_speed_px_per_sec:
                queue_length += 1

        vehicle_count = sum(vehicle_count_by_class.values())
        occupancy = min(1.0, total_bbox_area / frame_area)
        density = min(1.0, 0.65 * occupancy + 0.35 * (queue_length / max(vehicle_count, 1)))
        average_speed = round(sum(speed_samples) / max(len(speed_samples), 1), 2)
        waiting_time = round(sum(waiting_samples) / max(len(waiting_samples), 1), 2)

        traffic_level = self._traffic_level_from_state(
            queue_length=queue_length,
            density=density,
            occupancy=occupancy,
            average_speed=average_speed,
            waiting_time=waiting_time,
        )

        return {
            "vehicle_count": vehicle_count,
            "vehicle_count_by_class": vehicle_count_by_class,
            "queue_length": queue_length,
            "density": round(density, 3),
            "average_speed": average_speed,
            "occupancy": round(occupancy, 3),
            "waiting_time": waiting_time,
            "traffic_level": traffic_level,
        }

    def _snapshot_score(self, traffic_state: Dict[str, object]) -> float:
        vehicle_count = float(traffic_state.get("vehicle_count", 0))
        pcu_demand = float(traffic_state.get("pcu_demand", 0.0))
        queue_length = float(traffic_state.get("queue_length", 0))
        density = float(traffic_state.get("density", 0.0))
        occupancy = float(traffic_state.get("occupancy", 0.0))
        # Prefer dense stop-line snapshots when scanning timelapse footage.
        return round(vehicle_count * 2.0 + pcu_demand + queue_length * 1.5 + density * 10.0 + occupancy * 5.0, 3)

    def _aggregate_peak_snapshots(self, snapshots: List[Dict[str, object]]) -> Tuple[Dict[str, object], int]:
        if not snapshots:
            return {}, 0

        ordered = sorted(snapshots, key=lambda item: float(item.get("score", 0.0)), reverse=True)
        best_score = float(ordered[0].get("score", 0.0))
        peak_cutoff = max(best_score * 0.8, best_score - 2.5)
        peak_snapshots = [snapshot for snapshot in ordered if float(snapshot.get("score", 0.0)) >= peak_cutoff][:5]

        aggregated_counts = {"car": 0, "bus": 0, "auto": 0, "truck": 0, "bike": 0}
        for class_name in aggregated_counts.keys():
            aggregated_counts[class_name] = max(
                int(snapshot["vehicle_count_by_class"].get(class_name, 0))
                for snapshot in peak_snapshots
            )

        vehicle_count = sum(aggregated_counts.values())
        queue_length = max(int(snapshot["queue_length"]) for snapshot in peak_snapshots)
        occupancy = max(float(snapshot["occupancy"]) for snapshot in peak_snapshots)
        density = max(float(snapshot["density"]) for snapshot in peak_snapshots)
        waiting_time = max(float(snapshot["waiting_time"]) for snapshot in peak_snapshots)

        average_speed = min(float(snapshot["average_speed"]) for snapshot in peak_snapshots)
        if vehicle_count > 0 and average_speed > self.CONSTANTS.speed_medium:
            # Timelapse clips often distort motion enough that a physical speed is
            # not trustworthy. Clamp to a conservative stop-queue proxy.
            average_speed = 0.0

        return {
            "vehicle_count": vehicle_count,
            "vehicle_count_by_class": aggregated_counts,
            "queue_length": queue_length,
            "density": round(density, 3),
            "average_speed": round(average_speed, 2),
            "occupancy": round(occupancy, 3),
            "waiting_time": round(waiting_time, 2),
            "traffic_level": self._traffic_level_from_state(
                queue_length=queue_length,
                density=density,
                occupancy=occupancy,
                average_speed=average_speed,
                waiting_time=waiting_time,
            ),
        }, len(peak_snapshots)

    def _compute_demand_rate(self, pcu_demand: float, observation_window_sec: float) -> float:
        observation_window_sec = max(float(observation_window_sec), 1.0)
        return round(float(pcu_demand) * 3600.0 / observation_window_sec, 2)

    def _calculate_webster_timing(
        self,
        junction_name: str,
        direction: str,
        source_kind: str,
        pcu_demand: float,
        observation_window_sec: float,
    ) -> Dict[str, object]:
        min_green_sec, max_green_sec, default_cycle_sec = self._get_system_limits()

        current_state = AdaptiveSignalState.query.filter_by(
            junction_name=junction_name,
            direction=direction,
        ).first()
        if current_state is None:
            current_state = self._build_empty_state(junction_name, direction, source_kind)
            db.session.add(current_state)

        current_state.pcu_demand = round(float(pcu_demand), 2)
        current_state.demand_rate_pcu_per_hr = self._compute_demand_rate(pcu_demand, observation_window_sec)
        current_state.source_kind = source_kind
        current_state.updated_at = datetime.utcnow()
        db.session.flush()

        states = self._ensure_direction_rows(junction_name, source_kind)
        states[direction] = current_state

        y_values: Dict[str, float] = {}
        for dir_name, state in states.items():
            y_values[dir_name] = round(float(state.demand_rate_pcu_per_hr or 0.0) / self.CONSTANTS.saturation_flow_pcu_per_hr, 4)

        y_total = round(sum(y_values.values()), 4)
        min_cycle_floor = self.CONSTANTS.lost_time_sec + len(self.DIRECTIONS) * min_green_sec
        if y_total >= 0.95:
            cycle_length = max(default_cycle_sec, min_cycle_floor, self.CONSTANTS.lost_time_sec + 4 * max_green_sec)
            webster_status = "oversaturated"
        else:
            webster_cycle = (1.5 * self.CONSTANTS.lost_time_sec + 5.0) / max(1.0 - y_total, 0.05)
            cycle_length = max(webster_cycle, default_cycle_sec, min_cycle_floor)
            webster_status = "ok"

        direction_count = len(self.DIRECTIONS)
        min_total_green = direction_count * min_green_sec
        max_total_green = direction_count * max_green_sec
        green_pool = max(cycle_length - self.CONSTANTS.lost_time_sec, min_total_green)
        green_pool = min(green_pool, max_total_green)

        # First guarantee minimum green for every direction, then distribute
        # only the residual pool by demand ratio with max-cap rebalancing.
        bounded_green_times: Dict[str, float] = {
            dir_name: float(min_green_sec) for dir_name in self.DIRECTIONS
        }
        remaining_green = max(0.0, green_pool - min_total_green)
        active_dirs = set(self.DIRECTIONS)

        while remaining_green > 1e-6 and active_dirs:
            total_weight = sum(max(y_values[d], 0.0) for d in active_dirs)
            if total_weight <= 0.0:
                target_add = {d: remaining_green / len(active_dirs) for d in active_dirs}
            else:
                target_add = {d: (remaining_green * max(y_values[d], 0.0)) / total_weight for d in active_dirs}

            consumed = 0.0
            saturated_dirs = set()
            for dir_name in active_dirs:
                room = max(0.0, max_green_sec - bounded_green_times[dir_name])
                addition = min(target_add[dir_name], room)
                bounded_green_times[dir_name] += addition
                consumed += addition
                if room - addition <= 1e-6:
                    saturated_dirs.add(dir_name)

            if consumed <= 1e-6:
                break

            remaining_green = max(0.0, remaining_green - consumed)
            active_dirs -= saturated_dirs

        signal_plan: Dict[str, dict] = {}

        for dir_name in self.DIRECTIONS:
            y_i = y_values[dir_name]
            green_time = max(min_green_sec, min(bounded_green_times[dir_name], max_green_sec))
            signal_plan[dir_name] = {
                "direction": dir_name,
                "direction_label": self.DIRECTION_LABELS[dir_name],
                "critical_flow_ratio": round(y_i, 4),
                "green_time_sec": round(green_time, 2),
            }
            state = states[dir_name]
            state.green_time_sec = round(green_time, 2)
            state.updated_at = datetime.utcnow()

        db.session.commit()

        return {
            "status": webster_status,
            "cycle_length_sec": round(cycle_length, 2),
            "lost_time_sec": self.CONSTANTS.lost_time_sec,
            "critical_flow_ratios": y_values,
            "critical_flow_ratio_sum": y_total,
            "signal_plan": [signal_plan[dir_name] for dir_name in self.DIRECTIONS],
            "green_time_sec": signal_plan[direction]["green_time_sec"],
        }

    def _finalize_response(
        self,
        junction_name: str,
        direction: str,
        source_kind: str,
        traffic_state: Dict[str, object],
        pcu: Dict[str, object],
        congestion: Dict[str, object],
        webster: Dict[str, object],
    ) -> Dict[str, object]:
        vehicle_count_by_class = dict(traffic_state["vehicle_count_by_class"])
        vehicle_count_total = int(traffic_state["vehicle_count"])

        # ── Persist analytics to database ────────────────────────────────────
        try:
            self._persist_signal_decision(
                junction_name, direction, source_kind,
                vehicle_count_total, vehicle_count_by_class,
                traffic_state, pcu, congestion, webster,
            )
        except Exception as _persist_exc:
            logger.warning("Failed to persist signal decision: %s", _persist_exc)
        # ─────────────────────────────────────────────────────────────────────

        return {
            "junction": junction_name,
            "direction": direction,
            "source_kind": source_kind,
            "vehicle_count": {
                **vehicle_count_by_class,
                "total": vehicle_count_total,
            },
            "traffic_state": {
                "queue_length": traffic_state["queue_length"],
                "density": traffic_state["density"],
                "average_speed": traffic_state["average_speed"],
                "occupancy": traffic_state["occupancy"],
                "waiting_time": traffic_state["waiting_time"],
                "traffic_level": traffic_state["traffic_level"],
            },
            "pcu": {
                "factors": pcu["pcu_factors"],
                "demand": pcu["pcu_demand"],
            },
            "congestion": {
                "level": congestion["level"],
                "score": congestion["score"],
                "pcu_demand": congestion["pcu_demand"],
                "density": congestion["density"],
                "queue_length": congestion["queue_length"],
            },
            "signal": {
                "green_time": webster["green_time_sec"],
                "unit": "seconds",
                "current_direction": self.DIRECTION_LABELS[direction],
                "sequence": [self.DIRECTION_LABELS[d] for d in self.DIRECTIONS],
            },
            "webster": webster,
        }

    # ------------------------------------------------------------------
    # Persistence helpers (new)
    # ------------------------------------------------------------------
    def _persist_signal_decision(
        self,
        junction_name: str,
        direction: str,
        source_kind: str,
        vehicle_count_total: int,
        vehicle_count_by_class: Dict[str, int],
        traffic_state: Dict[str, object],
        pcu: Dict[str, object],
        congestion: Dict[str, object],
        webster: Dict[str, object],
    ) -> None:
        """
        Write TrafficStateSnapshot, SignalDecision, DecisionLog, and
        TrafficTrend rows for this pipeline result.

        All writes are flushed inside the existing SQLAlchemy session so
        they commit with the caller's session lifecycle.
        """
        from app.models.traffic_state_snapshot import TrafficStateSnapshot
        from app.models.signal_decision import SignalDecision
        from app.models.decision_log import DecisionLog
        from app.models.traffic_trend import TrafficTrend

        now = datetime.utcnow()

        # Look up the Junction row for the FK (nullable — don't fail if absent)
        j_obj = Junction.query.filter_by(name=junction_name).first()
        j_id  = j_obj.id if j_obj else None

        # 1. TrafficStateSnapshot ────────────────────────────────────────────
        snap = TrafficStateSnapshot(
            junction_id      = j_id,
            junction_name    = junction_name,
            direction        = direction,
            vehicle_count    = vehicle_count_total,
            car_count        = vehicle_count_by_class.get("car", 0),
            bus_count        = vehicle_count_by_class.get("bus", 0),
            truck_count      = vehicle_count_by_class.get("truck", 0),
            bike_count       = vehicle_count_by_class.get("bike", 0),
            auto_count       = vehicle_count_by_class.get("auto", 0),
            queue_length     = int(traffic_state["queue_length"]),
            density          = float(traffic_state["density"]),
            speed            = float(traffic_state["average_speed"]),
            occupancy        = float(traffic_state["occupancy"]),
            waiting_time     = float(traffic_state["waiting_time"]),
            traffic_level    = str(traffic_state["traffic_level"]),
            pcu_demand       = float(pcu["pcu_demand"]),
            congestion_level = str(congestion["level"]),
            source_kind      = source_kind,
            captured_at      = now,
        )
        db.session.add(snap)

        # 2. SignalDecision ───────────────────────────────────────────────────
        green_time = float(webster.get("green_time_sec", 0.0))
        cong_level = str(congestion["level"])
        traffic_level = str(traffic_state["traffic_level"])

        # Classify the decision type from change in green time
        prev_state = AdaptiveSignalState.query.filter_by(
            junction_name=junction_name, direction=direction
        ).first()
        prev_green  = float(prev_state.green_time_sec) if prev_state and prev_state.green_time_sec else None
        if prev_green is None:
            decision_type = "adaptive"
            reason = f"Initial adaptive calculation — {traffic_level} traffic, {cong_level} congestion"
        elif green_time > prev_green + 2:
            decision_type = "extend_green"
            reason = f"Extend GREEN {prev_green:.0f}s→{green_time:.0f}s (PCU={pcu['pcu_demand']:.1f}, {cong_level})"
        elif green_time < prev_green - 2:
            decision_type = "reduce_green"
            reason = f"Reduce GREEN {prev_green:.0f}s→{green_time:.0f}s (PCU={pcu['pcu_demand']:.1f}, {cong_level})"
        else:
            decision_type = "adaptive"
            reason = f"Hold GREEN {green_time:.0f}s (PCU={pcu['pcu_demand']:.1f}, {cong_level})"

        sig_dec = SignalDecision(
            junction_id            = j_id,
            junction_name          = junction_name,
            direction              = direction,
            vehicle_count          = vehicle_count_total,
            pcu                    = float(pcu["pcu_demand"]),
            density                = float(traffic_state["density"]),
            congestion_level       = cong_level,
            traffic_level          = traffic_level,
            recommended_green_time = green_time,
            previous_green_time    = prev_green,
            cycle_length_sec       = float(webster.get("cycle_length_sec", 0.0)),
            decision_type          = decision_type,
            reason                 = reason,
            source_kind            = source_kind,
            created_at             = now,
        )
        db.session.add(sig_dec)
        db.session.flush()  # get sig_dec.id

        # 3. DecisionLog ─────────────────────────────────────────────────────
        log_entry = DecisionLog(
            module             = "adaptive_signal",
            junction_id        = j_id,
            junction_name      = junction_name,
            direction          = direction.upper(),
            decision           = decision_type.replace("_", " ").upper(),
            reason             = reason,
            traffic_level      = traffic_level,
            congestion_level   = cong_level,
            pcu                = float(pcu["pcu_demand"]),
            density            = float(traffic_state["density"]),
            green_time         = green_time,
            signal_decision_id = sig_dec.id,
            metadata_          = {
                "vehicle_count_by_class": vehicle_count_by_class,
                "queue_length":           int(traffic_state["queue_length"]),
                "occupancy":              float(traffic_state["occupancy"]),
                "waiting_time":           float(traffic_state["waiting_time"]),
                "signal_plan":            webster.get("signal_plan", []),
                "cycle_length_sec":       float(webster.get("cycle_length_sec", 0.0)),
                "source_kind":            source_kind,
            },
            created_at         = now,
        )
        db.session.add(log_entry)

        # 4. TrafficTrend (5-minute buckets) ─────────────────────────────────
        # Round now down to the nearest 5-minute boundary
        bucket_minute = (now.minute // 5) * 5
        bucket = now.replace(minute=bucket_minute, second=0, microsecond=0)

        # Upsert: update existing bucket row or insert a new one
        trend_row = TrafficTrend.query.filter_by(
            junction_id=j_id,
            time_bucket=bucket,
        ).first()
        if trend_row is None:
            trend_row = TrafficTrend(
                junction_id      = j_id,
                junction_name    = junction_name,
                time_bucket      = bucket,
                vehicle_count    = vehicle_count_total,
                pcu              = float(pcu["pcu_demand"]),
                congestion_level = cong_level,
                average_speed    = float(traffic_state["average_speed"]),
                traffic_level    = traffic_level,
                created_at       = now,
            )
            db.session.add(trend_row)
        else:
            # Accumulate within the bucket window
            trend_row.vehicle_count    = max(trend_row.vehicle_count, vehicle_count_total)
            trend_row.pcu              = max(trend_row.pcu, float(pcu["pcu_demand"]))
            # Prefer the worse congestion level
            _level_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
            if _level_order.get(cong_level, 0) >= _level_order.get(trend_row.congestion_level, 0):
                trend_row.congestion_level = cong_level
                trend_row.traffic_level    = traffic_level

        db.session.flush()

    def process_image(self, image_bytes: bytes, junction_name: str, direction: str) -> Dict[str, object]:
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Unable to decode uploaded image")

        detections = self._detect_frame(frame)
        traffic_state = self._estimate_traffic_state_from_detections(detections, frame.shape[:2])
        pcu = self.calculate_pcu(traffic_state["vehicle_count_by_class"])
        congestion = self.estimate_congestion(pcu["pcu_demand"], traffic_state)
        states = self._ensure_direction_rows(junction_name, "image")
        current_state = states[direction]
        current_state.vehicle_count_total = traffic_state["vehicle_count"]
        current_state.vehicle_count_by_class = dict(traffic_state["vehicle_count_by_class"])
        current_state.queue_length = traffic_state["queue_length"]
        current_state.density = traffic_state["density"]
        current_state.average_speed = traffic_state["average_speed"]
        current_state.occupancy = traffic_state["occupancy"]
        current_state.waiting_time = traffic_state["waiting_time"]
        current_state.traffic_level = traffic_state["traffic_level"]
        current_state.pcu_demand = pcu["pcu_demand"]
        current_state.congestion_level = congestion["level"]
        current_state.source_kind = "image"
        current_state.updated_at = datetime.utcnow()
        db.session.flush()

        webster = self._calculate_webster_timing(
            junction_name=junction_name,
            direction=direction,
            source_kind="image",
            pcu_demand=pcu["pcu_demand"],
            observation_window_sec=self.CONSTANTS.image_observation_window_sec,
        )
        return self._finalize_response(junction_name, direction, "image", traffic_state, pcu, congestion, webster)

    def process_video(self, video_path: Path, junction_name: str, direction: str) -> Dict[str, object]:
        video_path = video_path.resolve()
        if not video_path.is_file():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError("Unable to open uploaded video")

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        frame_count = 0
        first_frame_shape: Optional[Tuple[int, int]] = None
        sampled_snapshots: List[Dict[str, object]] = []
        sample_step = max(1, int(round(fps / 2.0)))

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                if first_frame_shape is None:
                    first_frame_shape = frame.shape[:2]

                if frame_count % sample_step == 0:
                    detections = self._detect_frame(frame)
                    if detections:
                        snapshot_state = self._estimate_traffic_state_from_detections(detections, frame.shape[:2])
                        snapshot_state["score"] = self._snapshot_score(snapshot_state)
                        snapshot_state["frame_index"] = frame_count
                        sampled_snapshots.append(snapshot_state)

                frame_count += 1
        finally:
            cap.release()

        if first_frame_shape is None:
            raise ValueError("Uploaded video does not contain readable frames")

        # Use the strongest stop-line snapshots from the clip. This is more
        # stable for timelapse footage where the important information is the
        # repeated red-phase queue, not frame-to-frame motion.
        traffic_state, stop_events = self._aggregate_peak_snapshots(sampled_snapshots)
        if not traffic_state:
            traffic_state = self._estimate_traffic_state_from_tracks({}, first_frame_shape)
            stop_events = 0

        if stop_events <= 0:
            stop_events = 1

        pcu = self.calculate_pcu(traffic_state["vehicle_count_by_class"])
        congestion = self.estimate_congestion(pcu["pcu_demand"], traffic_state)
        states = self._ensure_direction_rows(junction_name, "video")
        current_state = states[direction]
        current_state.vehicle_count_total = traffic_state["vehicle_count"]
        current_state.vehicle_count_by_class = dict(traffic_state["vehicle_count_by_class"])
        current_state.queue_length = traffic_state["queue_length"]
        current_state.density = traffic_state["density"]
        current_state.average_speed = traffic_state["average_speed"]
        current_state.occupancy = traffic_state["occupancy"]
        current_state.waiting_time = traffic_state["waiting_time"]
        current_state.traffic_level = traffic_state["traffic_level"]
        current_state.pcu_demand = pcu["pcu_demand"]
        current_state.congestion_level = congestion["level"]
        current_state.source_kind = "video"
        current_state.updated_at = datetime.utcnow()
        db.session.flush()

        # Scale the observation window by the number of repeated stop cycles so
        # Webster demand is based on the repeated red-light observations.
        duration_sec = max(frame_count / fps, stop_events * self.CONSTANTS.image_observation_window_sec)
        webster = self._calculate_webster_timing(
            junction_name=junction_name,
            direction=direction,
            source_kind="video",
            pcu_demand=pcu["pcu_demand"],
            observation_window_sec=duration_sec,
        )
        return self._finalize_response(junction_name, direction, "video", traffic_state, pcu, congestion, webster)

    def process(self, uploaded_file_name: str, file_bytes: bytes, junction_name: str, direction: str) -> Dict[str, object]:
        file_kind = self._supported_file_kind(uploaded_file_name)
        if file_kind is None:
            raise ValueError("unsupported file type")

        self.validate_junction(junction_name)

        direction = direction.strip().lower()
        if direction not in self.DIRECTIONS:
            raise ValueError("invalid direction")

        if file_kind == "image":
            return self.process_image(file_bytes, junction_name, direction)

        temp_path: Optional[Path] = None
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file_name).suffix.lower()) as temp_file:
            temp_file.write(file_bytes)
            temp_path = Path(temp_file.name)

        try:
            return self.process_video(temp_path, junction_name, direction)
        finally:
            if temp_path is not None:
                try:
                    os.unlink(temp_path)
                except OSError:
                    logger.debug("Could not remove temp file %s", temp_path)


adaptive_signal_pipeline = AdaptiveSignalPipeline()