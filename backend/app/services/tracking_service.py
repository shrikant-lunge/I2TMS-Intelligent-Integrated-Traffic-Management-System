"""
Tracking Service - Centroid-based multi-object tracker.
Maintains consistent track IDs across frames.
"""

import time
import logging
import math
from typing import List, Dict, Optional, Tuple
from collections import OrderedDict

from app.config import MAX_DISAPPEARED_FRAMES, MAX_TRACK_DISTANCE, MIN_MOVEMENT_THRESHOLD

logger = logging.getLogger(__name__)


class TrackedVehicle:
    """Represents a tracked vehicle across frames."""

    def __init__(self, track_id: int, centroid: Tuple[int, int], bbox: List[int],
                 class_name: str, confidence: float):
        self.track_id = track_id
        self.class_name = class_name
        self.confidence = confidence
        self.centroids: List[Tuple[int, int]] = [centroid]
        self.bboxes: List[List[int]] = [bbox]
        self.first_seen: float = time.time()
        self.last_seen: float = time.time()
        self.disappeared: int = 0
        self.movement_status: str = "MOVING"
        self.in_corridor: bool = False
        self.corridor_enter_time: Optional[float] = None
        self.blocking_time: float = 0.0
        self.violation_flagged: bool = False

    @property
    def current_centroid(self) -> Tuple[int, int]:
        return self.centroids[-1]

    @property
    def current_bbox(self) -> List[int]:
        return self.bboxes[-1]

    def update(self, centroid: Tuple[int, int], bbox: List[int],
               confidence: float):
        """Update track with new detection."""
        self.centroids.append(centroid)
        self.bboxes.append(bbox)
        self.last_seen = time.time()
        self.disappeared = 0
        self.confidence = max(self.confidence, confidence)

        # Keep only last 60 positions to limit memory
        if len(self.centroids) > 60:
            self.centroids = self.centroids[-60:]
            self.bboxes = self.bboxes[-60:]

        # Update movement status
        self._classify_movement()

    def _classify_movement(self):
        """Classify vehicle movement based on recent centroids."""
        if len(self.centroids) < 5:
            self.movement_status = "MOVING"
            return

        # Compare recent positions
        recent = self.centroids[-10:]  # Last 10 positions
        if len(recent) < 3:
            return

        # Calculate total displacement over recent frames
        total_displacement = 0.0
        for i in range(1, len(recent)):
            dx = recent[i][0] - recent[i - 1][0]
            dy = recent[i][1] - recent[i - 1][1]
            total_displacement += math.sqrt(dx * dx + dy * dy)

        avg_displacement = total_displacement / len(recent)

        if avg_displacement < 2:
            self.movement_status = "STOPPED"
        elif avg_displacement < MIN_MOVEMENT_THRESHOLD / 3:
            self.movement_status = "SLOW"
        else:
            # Check if moving away (y decreasing = moving away from camera)
            if len(recent) >= 3:
                y_diff = recent[-1][1] - recent[-3][1]
                if y_diff < -10:
                    self.movement_status = "CLEARING"
                else:
                    self.movement_status = "MOVING"
            else:
                self.movement_status = "MOVING"

    def update_corridor_status(self, in_corridor: bool):
        """Update corridor blocking state."""
        now = time.time()
        if in_corridor and not self.in_corridor:
            self.corridor_enter_time = now
            self.in_corridor = True
        elif not in_corridor and self.in_corridor:
            self.in_corridor = False
            self.corridor_enter_time = None
            self.blocking_time = 0.0

        if self.in_corridor and self.corridor_enter_time:
            self.blocking_time = now - self.corridor_enter_time

    def mark_disappeared(self):
        """Mark vehicle as disappeared for one frame."""
        self.disappeared += 1


class VehicleTracker:
    """Centroid-based multi-object tracker."""

    def __init__(self):
        self._next_id: int = 1
        self._vehicles: OrderedDict[int, TrackedVehicle] = OrderedDict()
        self._max_disappeared = MAX_DISAPPEARED_FRAMES
        self._max_distance = MAX_TRACK_DISTANCE

    @property
    def vehicles(self) -> Dict[int, TrackedVehicle]:
        return dict(self._vehicles)

    def update(self, detections: List[dict]) -> Dict[int, TrackedVehicle]:
        """
        Update tracker with new detections.

        Args:
            detections: List of {"center": [cx, cy], "bbox": [x1,y1,x2,y2],
                                  "class_name": str, "confidence": float}

        Returns:
            Dict of track_id -> TrackedVehicle
        """
        # If no detections, mark all as disappeared
        if len(detections) == 0:
            for track_id in list(self._vehicles.keys()):
                self._vehicles[track_id].mark_disappeared()
                if self._vehicles[track_id].disappeared > self._max_disappeared:
                    del self._vehicles[track_id]
            return self.vehicles

        # Extract centroids from detections
        input_centroids = []
        for d in detections:
            input_centroids.append(tuple(d["center"]))

        # If no existing tracks, register all
        if len(self._vehicles) == 0:
            for i, centroid in enumerate(input_centroids):
                self._register(
                    centroid,
                    detections[i]["bbox"],
                    detections[i]["class_name"],
                    detections[i]["confidence"],
                )
            return self.vehicles

        # Match existing tracks to new detections using distance
        track_ids = list(self._vehicles.keys())
        track_centroids = [self._vehicles[tid].current_centroid for tid in track_ids]

        # Compute distance matrix
        dist_matrix = []
        for tc in track_centroids:
            row = []
            for ic in input_centroids:
                d = math.sqrt((tc[0] - ic[0]) ** 2 + (tc[1] - ic[1]) ** 2)
                row.append(d)
            dist_matrix.append(row)

        # Greedy matching (simple Hungarian alternative)
        used_tracks = set()
        used_detections = set()
        matches = []

        # Sort all pairs by distance
        pairs = []
        for i in range(len(track_ids)):
            for j in range(len(input_centroids)):
                pairs.append((dist_matrix[i][j], i, j))
        pairs.sort(key=lambda x: x[0])

        for dist, ti, di in pairs:
            if ti in used_tracks or di in used_detections:
                continue
            if dist > self._max_distance:
                continue
            matches.append((ti, di))
            used_tracks.add(ti)
            used_detections.add(di)

        # Update matched tracks
        for ti, di in matches:
            tid = track_ids[ti]
            self._vehicles[tid].update(
                input_centroids[di],
                detections[di]["bbox"],
                detections[di]["confidence"],
            )

        # Mark unmatched tracks as disappeared
        for i in range(len(track_ids)):
            if i not in used_tracks:
                tid = track_ids[i]
                self._vehicles[tid].mark_disappeared()
                if self._vehicles[tid].disappeared > self._max_disappeared:
                    del self._vehicles[tid]

        # Register unmatched detections as new tracks
        for j in range(len(input_centroids)):
            if j not in used_detections:
                self._register(
                    input_centroids[j],
                    detections[j]["bbox"],
                    detections[j]["class_name"],
                    detections[j]["confidence"],
                )

        return self.vehicles

    def _register(self, centroid: Tuple[int, int], bbox: List[int],
                  class_name: str, confidence: float):
        """Register a new tracked vehicle."""
        vehicle = TrackedVehicle(
            self._next_id, centroid, bbox, class_name, confidence,
        )
        self._vehicles[self._next_id] = vehicle
        self._next_id += 1

    def reset(self):
        """Clear all tracks."""
        self._vehicles.clear()
        self._next_id = 1

    def get_vehicle_info(self, track_id: int) -> Optional[TrackedVehicle]:
        """Get info for a specific tracked vehicle."""
        return self._vehicles.get(track_id)


# Singleton
vehicle_tracker = VehicleTracker()
