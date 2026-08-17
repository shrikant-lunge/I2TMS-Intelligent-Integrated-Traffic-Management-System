"""
Processing Pipeline - Orchestrates the complete detection-to-violation pipeline.
Runs in a background thread, coordinating all services.
"""

import cv2
import time
import logging
import threading
import datetime
from typing import Optional, List
from collections import deque

import numpy as np

from app.config import FRAME_SKIP, EVIDENCE_DIR
from app.services.camera_service import camera_service
from app.services.detection_service import detect_vehicles
from app.services.tracking_service import vehicle_tracker, TrackedVehicle
from app.services.corridor_service import corridor_service
from app.services.plate_service import detect_plate
from app.services.ocr_service import read_plate
from app.services.evidence_service import save_evidence
from app.services.emergency_service import emergency_service
from app.services.gps_service import gps_service
from app.models.database import ViolationDB, SessionLocal

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """Main video processing pipeline orchestrator."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._frame_counter: int = 0
        self._violation_counter: int = 0

        # Live state for API/frontend consumption
        self._current_annotated_frame: Optional[np.ndarray] = None
        self._current_vehicles: List[dict] = []
        self._recent_violations: deque = deque(maxlen=50)
        self._corridor_polygon: List[List[int]] = []
        # Preserve the best model/OCR reading for a track. This mirrors the
        # supplied ANPR demo's stable labels instead of letting plate text
        # disappear on frames where OCR has no fresh result.
        self._plate_cache: dict[int, dict] = {}

    @property
    def running(self) -> bool:
        return self._running

    @property
    def current_frame(self) -> Optional[np.ndarray]:
        return self._current_annotated_frame

    @property
    def current_vehicles(self) -> List[dict]:
        return list(self._current_vehicles)

    @property
    def recent_violations(self) -> list:
        return list(self._recent_violations)

    @property
    def corridor_polygon(self) -> List[List[int]]:
        return self._corridor_polygon

    def start(self):
        """Start the processing pipeline in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Processing pipeline started")

    def stop(self):
        """Stop the processing pipeline."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._current_annotated_frame = None
        self._current_vehicles = []
        self._plate_cache.clear()
        logger.info("Processing pipeline stopped")

    def _run(self):
        """Main processing loop."""
        while self._running:
            try:
                # Read frame
                frame = camera_service.read_frame()
                if frame is None:
                    time.sleep(0.05)
                    continue

                self._frame_counter += 1

                # Frame skipping for performance
                if self._frame_counter % (FRAME_SKIP + 1) != 0:
                    # Still update the display frame even on skipped frames
                    with self._lock:
                        self._current_annotated_frame = self._annotate_frame(
                            frame, [], {}
                        )
                    time.sleep(0.01)
                    continue

                # Get frame dimensions and update corridor
                h, w = frame.shape[:2]
                corridor_service.update_frame_size(w, h)
                self._corridor_polygon = corridor_service.get_polygon_points()

                # --- VEHICLE DETECTION ---
                detections = detect_vehicles(frame)

                # --- VEHICLE TRACKING ---
                tracked = vehicle_tracker.update(detections)

                # --- PLATE READOUT FOR LIVE FEED ---
                vehicle_infos = []
                for track_id, vehicle in tracked.items():
                    x1, y1, x2, y2 = vehicle.current_bbox
                    x1 = max(0, int(x1))
                    y1 = max(0, int(y1))
                    x2 = min(frame.shape[1], int(x2))
                    y2 = min(frame.shape[0], int(y2))
                    vehicle_crop = frame[y1:y2, x1:x2]

                    cached_plate = self._plate_cache.get(vehicle.track_id, {})
                    plate_number = cached_plate.get("plate_number")
                    plate_confidence = cached_plate.get("plate_confidence")
                    plate_bbox = cached_plate.get("plate_bbox")
                    if vehicle_crop.size > 0:
                        plate_result = detect_plate(vehicle_crop)
                        if plate_result is not None:
                            ocr_result = read_plate(plate_result["plate_crop"])
                            detected_text = ocr_result.get("normalized_text") or ocr_result.get("raw_text")
                            detected_confidence = float(ocr_result.get("confidence") or 0.0)
                            if detected_text and ocr_result.get("status") in {"OK", "NEEDS_REVIEW"}:
                                relative_bbox = plate_result.get("plate_bbox", [0, 0, 0, 0])
                                absolute_bbox = [
                                    x1 + int(relative_bbox[0]),
                                    y1 + int(relative_bbox[1]),
                                    x1 + int(relative_bbox[2]),
                                    y1 + int(relative_bbox[3]),
                                ]
                                previous_confidence = float(cached_plate.get("plate_confidence") or 0.0)
                                if detected_confidence >= previous_confidence:
                                    self._plate_cache[vehicle.track_id] = {
                                        "plate_number": detected_text,
                                        "plate_confidence": detected_confidence,
                                        "plate_bbox": absolute_bbox,
                                        "detector": plate_result.get("detector", "unknown"),
                                    }
                                    plate_number = detected_text
                                    plate_confidence = detected_confidence
                                    plate_bbox = absolute_bbox

                    vehicle_infos.append({
                        "tracking_id": vehicle.track_id,
                        "vehicle_type": vehicle.class_name,
                        "confidence": vehicle.confidence,
                        "bbox": vehicle.current_bbox,
                        "center": list(vehicle.current_centroid),
                        "movement_status": vehicle.movement_status,
                        "in_corridor": vehicle.in_corridor,
                        "blocking_time": round(vehicle.blocking_time, 1),
                        "first_seen": datetime.datetime.fromtimestamp(
                            vehicle.first_seen
                        ).isoformat(),
                        "plate_number": plate_number,
                        "plate_confidence": plate_confidence,
                        "plate_bbox": plate_bbox,
                    })

                # --- CORRIDOR CHECK & VIOLATION PIPELINE ---
                is_emergency = emergency_service.is_active
                event_id = emergency_service.active_event_id

                for track_id, vehicle in tracked.items():
                    # Check corridor and violations
                    violation_info = None
                    if is_emergency and event_id:
                        violation_info = corridor_service.check_violation(
                            vehicle, event_id, is_emergency
                        )

                    # Even when not in emergency, still track corridor position for display
                    if not is_emergency:
                        cx, cy = vehicle.current_centroid
                        in_corridor = corridor_service.is_in_corridor(cx, cy)
                        vehicle.update_corridor_status(in_corridor)

                    # Build vehicle info for API
                    info = next(
                        item for item in vehicle_infos if item["tracking_id"] == vehicle.track_id
                    )

                    # --- VIOLATION PROCESSING ---
                    if violation_info is not None:
                        self._process_violation(
                            frame, vehicle, violation_info, event_id
                        )

                # Update shared state
                with self._lock:
                    self._current_vehicles = vehicle_infos
                    self._current_annotated_frame = self._annotate_frame(
                        frame, vehicle_infos, tracked
                    )

                # Throttle to ~30 FPS max
                time.sleep(0.01)

            except Exception as e:
                logger.error(f"Pipeline error: {e}", exc_info=True)
                time.sleep(0.1)

    def _process_violation(
        self,
        frame: np.ndarray,
        vehicle: TrackedVehicle,
        violation_info: dict,
        emergency_event_id: str,
    ):
        """Process a confirmed violation: plate detection, OCR, evidence."""
        self._violation_counter += 1
        violation_id = f"EV-{self._violation_counter:04d}"

        # Get vehicle crop
        x1, y1, x2, y2 = vehicle.current_bbox
        h, w = frame.shape[:2]
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)
        vehicle_crop = frame[y1:y2, x1:x2].copy()

        # --- NUMBER PLATE DETECTION ---
        plate_result = detect_plate(vehicle_crop)
        plate_crop = None
        plate_number = None
        plate_confidence = None
        ocr_status = "NO_PLATE_DETECTED"

        if plate_result is not None:
            plate_crop = plate_result["plate_crop"]
            plate_confidence = plate_result["confidence"]

            # --- OCR ---
            ocr_result = read_plate(plate_crop)
            plate_number = ocr_result.get("normalized_text") or ocr_result.get("raw_text")
            plate_confidence = ocr_result.get("confidence", plate_confidence)
            ocr_status = ocr_result.get("status", "UNKNOWN")

            if not plate_number:
                plate_number = None

        # Determine violation status
        if plate_number and ocr_status == "OK":
            violation_status = "VERIFIED"
        elif plate_number and ocr_status == "NEEDS_REVIEW":
            violation_status = "NEEDS_REVIEW"
        else:
            violation_status = "DETECTED"  # Violation detected but plate unclear

        # --- GPS POSITION ---
        gps = gps_service.get_current_position()

        # --- EVIDENCE CAPTURE ---
        evidence_metadata = {
            "emergency_event_id": emergency_event_id,
            "vehicle_tracking_id": vehicle.track_id,
            "vehicle_type": vehicle.class_name,
            "plate_number": plate_number or "UNKNOWN",
            "plate_confidence": plate_confidence,
            "detection_confidence": vehicle.confidence,
            "blocking_duration": violation_info["blocking_duration"],
            "movement_status": violation_info["movement_status"],
            "latitude": gps.get("lat"),
            "longitude": gps.get("lon"),
            "violation_type": "EMERGENCY_CORRIDOR_BLOCKING",
            "ocr_status": ocr_status,
        }

        evidence_path = save_evidence(
            violation_id, frame, vehicle_crop, plate_crop, evidence_metadata
        )

        # --- DATABASE RECORD ---
        try:
            db = SessionLocal()
            violation_record = ViolationDB(
                violation_id=violation_id,
                emergency_event_id=emergency_event_id,
                vehicle_tracking_id=vehicle.track_id,
                vehicle_type=vehicle.class_name,
                plate_number=plate_number,
                plate_confidence=plate_confidence,
                detection_confidence=vehicle.confidence,
                violation_type="EMERGENCY_CORRIDOR_BLOCKING",
                latitude=gps.get("lat"),
                longitude=gps.get("lon"),
                evidence_path=str(evidence_path),
                blocking_duration=violation_info["blocking_duration"],
                movement_status=violation_info["movement_status"],
                status=violation_status,
            )
            db.add(violation_record)
            db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Failed to save violation to DB: {e}")

        # Add to recent violations for live display
        violation_display = {
            "violation_id": violation_id,
            "emergency_event_id": emergency_event_id,
            "vehicle_tracking_id": vehicle.track_id,
            "vehicle_type": vehicle.class_name,
            "plate_number": plate_number or "UNKNOWN",
            "plate_confidence": plate_confidence,
            "detection_confidence": vehicle.confidence,
            "violation_type": "EMERGENCY_CORRIDOR_BLOCKING",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "latitude": gps.get("lat"),
            "longitude": gps.get("lon"),
            "evidence_path": str(evidence_path),
            "blocking_duration": violation_info["blocking_duration"],
            "movement_status": violation_info["movement_status"],
            "status": violation_status,
        }
        self._recent_violations.appendleft(violation_display)

        logger.info(
            f"VIOLATION RECORDED: {violation_id}, plate={plate_number}, "
            f"type={vehicle.class_name}, status={violation_status}"
        )

    def _annotate_frame(
        self,
        frame: np.ndarray,
        vehicles: List[dict],
        tracked: dict,
    ) -> np.ndarray:
        """Draw detection overlays on frame."""
        annotated = frame.copy()
        h, w = annotated.shape[:2]

        is_emergency = emergency_service.is_active

        # Draw corridor polygon
        polygon = corridor_service.polygon
        if polygon is not None:
            overlay = annotated.copy()
            if is_emergency:
                # Red/orange corridor during emergency
                cv2.fillPoly(overlay, [polygon], (0, 50, 200))
                cv2.addWeighted(overlay, 0.2, annotated, 0.8, 0, annotated)
                cv2.polylines(annotated, [polygon], True, (0, 0, 255), 2)
                # Label
                cv2.putText(
                    annotated, "EMERGENCY CORRIDOR",
                    (polygon[0][0], polygon[0][1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2,
                )
            else:
                # Green corridor when not in emergency
                cv2.fillPoly(overlay, [polygon], (0, 150, 0))
                cv2.addWeighted(overlay, 0.1, annotated, 0.9, 0, annotated)
                cv2.polylines(annotated, [polygon], True, (0, 200, 0), 1)

        # Draw vehicle detections
        for v in vehicles:
            x1, y1, x2, y2 = v["bbox"]
            tid = v["tracking_id"]
            vtype = v["vehicle_type"]
            conf = v["confidence"]
            in_corr = v["in_corridor"]
            movement = v["movement_status"]
            plate_text = v.get("plate_number")

            # Color based on status
            if in_corr and is_emergency and movement in ("STOPPED", "SLOW"):
                color = (0, 0, 255)  # Red - potential violator
            elif in_corr:
                color = (0, 165, 255)  # Orange - in corridor
            else:
                color = (0, 255, 0)  # Green - normal

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            # Label
            label = f"ID:{tid} {vtype} {conf:.0%}"
            label_y = max(y1 - 5, 15)
            cv2.putText(
                annotated, label, (x1, label_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1,
            )

            if plate_text:
                plate_color = (255, 255, 255)
                px1, py1, px2, py2 = v.get("plate_bbox") or [0, 0, 0, 0]
                if px2 > px1 and py2 > py1:
                    cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 255, 255), 2)
                    plate_label_y = max(py1 - 6, 15)
                    cv2.putText(
                        annotated, f"PLATE: {plate_text}", (px1, plate_label_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2,
                    )
                cv2.putText(
                    annotated, f"Plate: {plate_text}", (x1, max(y2 + 28, label_y + 18)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, plate_color, 2,
                )

            # Show blocking time if in corridor
            if in_corr and v["blocking_time"] > 0:
                block_label = f"{movement} {v['blocking_time']:.1f}s"
                cv2.putText(
                    annotated, block_label, (x1, y2 + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1,
                )

        # Status overlay
        status_text = "EMERGENCY ACTIVE" if is_emergency else "NORMAL"
        status_color = (0, 0, 255) if is_emergency else (0, 200, 0)
        cv2.putText(
            annotated, status_text, (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2,
        )

        # Camera mode
        mode_text = f"Mode: {camera_service.mode}"
        cv2.putText(
            annotated, mode_text, (10, 55),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1,
        )

        # Vehicle count
        cv2.putText(
            annotated, f"Vehicles: {len(vehicles)}", (10, 75),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1,
        )

        return annotated

    def reset(self):
        """Reset pipeline state."""
        vehicle_tracker.reset()
        corridor_service.reset()
        self._current_vehicles = []
        self._recent_violations.clear()
        self._plate_cache.clear()
        self._frame_counter = 0


# Singleton
pipeline = ProcessingPipeline()
