"""
Corridor Service - Emergency corridor definition and violation detection.
"""

import logging
import time
from typing import List, Tuple, Optional, Set

import numpy as np

from app.config import (
    CORRIDOR_TOP_WIDTH_RATIO,
    CORRIDOR_BOTTOM_WIDTH_RATIO,
    CORRIDOR_TOP_Y_RATIO,
    CORRIDOR_BOTTOM_Y_RATIO,
    MIN_BLOCKING_TIME,
    MIN_DETECTION_CONFIDENCE,
)
from app.services.tracking_service import TrackedVehicle

logger = logging.getLogger(__name__)


class CorridorService:
    """Defines and manages the emergency corridor zone."""

    def __init__(self):
        self._corridor_polygon: Optional[np.ndarray] = None
        self._frame_width: int = 0
        self._frame_height: int = 0
        # Track which (event_id, track_id) combos have already generated violations
        self._violation_records: Set[Tuple[str, int]] = set()

    def update_frame_size(self, width: int, height: int):
        """Recalculate corridor polygon when frame size changes."""
        if width == self._frame_width and height == self._frame_height:
            return
        self._frame_width = width
        self._frame_height = height
        self._calculate_polygon()

    def _calculate_polygon(self):
        """Calculate the corridor polygon based on config ratios."""
        w = self._frame_width
        h = self._frame_height
        cx = w / 2

        top_y = int(h * CORRIDOR_TOP_Y_RATIO)
        bottom_y = int(h * CORRIDOR_BOTTOM_Y_RATIO)
        top_half_w = int(w * CORRIDOR_TOP_WIDTH_RATIO / 2)
        bottom_half_w = int(w * CORRIDOR_BOTTOM_WIDTH_RATIO / 2)

        # Trapezoid: narrower at top (far), wider at bottom (near camera)
        self._corridor_polygon = np.array([
            [cx - top_half_w, top_y],        # top-left
            [cx + top_half_w, top_y],        # top-right
            [cx + bottom_half_w, bottom_y],  # bottom-right
            [cx - bottom_half_w, bottom_y],  # bottom-left
        ], dtype=np.int32)

    @property
    def polygon(self) -> Optional[np.ndarray]:
        return self._corridor_polygon

    def get_polygon_points(self) -> List[List[int]]:
        """Get polygon as list of [x, y] points."""
        if self._corridor_polygon is None:
            return []
        return self._corridor_polygon.tolist()

    def is_in_corridor(self, cx: int, cy: int) -> bool:
        """Check if a point (vehicle center) is inside the corridor polygon."""
        if self._corridor_polygon is None:
            return False
        return self._point_in_polygon(cx, cy, self._corridor_polygon)

    @staticmethod
    def _point_in_polygon(px: int, py: int, polygon: np.ndarray) -> bool:
        """Ray-casting algorithm for point-in-polygon test."""
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def check_violation(
        self,
        vehicle: TrackedVehicle,
        emergency_event_id: str,
        emergency_active: bool,
    ) -> Optional[dict]:
        """
        Full violation decision pipeline:
        1. emergency_mode == ACTIVE
        2. Vehicle is inside emergency corridor
        3. Vehicle remains obstructing for MIN_BLOCKING_TIME
        4. Vehicle is not moving sufficiently (STOPPED or SLOW)
        5. Detection confidence is acceptable
        6. Not a duplicate for this event + track

        Returns violation info dict or None.
        """
        # Rule 1: Emergency must be active
        if not emergency_active:
            return None

        # Check corridor status
        cx, cy = vehicle.current_centroid
        in_corridor = self.is_in_corridor(cx, cy)
        vehicle.update_corridor_status(in_corridor)

        # Rule 2: Must be in corridor
        if not in_corridor:
            return None

        # Rule 3: Must be blocking for minimum time
        if vehicle.blocking_time < MIN_BLOCKING_TIME:
            return None

        # Rule 4: Must not be moving away / clearing
        if vehicle.movement_status in ("MOVING", "CLEARING"):
            return None

        # Rule 5: Detection confidence
        if vehicle.confidence < MIN_DETECTION_CONFIDENCE:
            return None

        # Rule 6: Duplicate prevention
        dup_key = (emergency_event_id, vehicle.track_id)
        if dup_key in self._violation_records:
            return None

        # All checks passed - this is a violation candidate
        self._violation_records.add(dup_key)
        vehicle.violation_flagged = True

        logger.info(
            f"VIOLATION CONFIRMED: Track {vehicle.track_id}, "
            f"type={vehicle.class_name}, blocking={vehicle.blocking_time:.1f}s, "
            f"movement={vehicle.movement_status}"
        )

        return {
            "vehicle_tracking_id": vehicle.track_id,
            "vehicle_type": vehicle.class_name,
            "detection_confidence": vehicle.confidence,
            "blocking_duration": round(vehicle.blocking_time, 2),
            "movement_status": vehicle.movement_status,
            "bbox": vehicle.current_bbox,
            "center": list(vehicle.current_centroid),
        }

    def reset(self):
        """Reset violation tracking for new emergency."""
        self._violation_records.clear()

    def clear_event_violations(self, event_id: str):
        """Clear violations for a specific event."""
        self._violation_records = {
            (eid, tid) for eid, tid in self._violation_records
            if eid != event_id
        }


# Singleton
corridor_service = CorridorService()
