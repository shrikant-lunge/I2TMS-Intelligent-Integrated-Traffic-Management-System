"""
Tests for Corridor Service - point-in-polygon, blocking time, movement classification.
"""

import sys
import os
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.corridor_service import CorridorService
from app.services.tracking_service import TrackedVehicle


class TestCorridorGeometry:
    """Test corridor polygon and point-in-polygon."""

    def setup_method(self):
        self.corridor = CorridorService()
        # Simulate a 640x480 frame
        self.corridor.update_frame_size(640, 480)

    def test_polygon_created(self):
        """Corridor polygon should be created after frame size update."""
        assert self.corridor.polygon is not None
        assert len(self.corridor.polygon) == 4  # Trapezoid

    def test_center_in_corridor(self):
        """Center of frame should be inside the corridor."""
        assert self.corridor.is_in_corridor(320, 350)

    def test_edge_outside_corridor(self):
        """Far left edge should be outside the corridor."""
        assert not self.corridor.is_in_corridor(10, 350)

    def test_top_outside_corridor(self):
        """Very top of frame should be outside the corridor."""
        assert not self.corridor.is_in_corridor(320, 10)


class TestViolationDecision:
    """Test the full violation decision pipeline."""

    def setup_method(self):
        self.corridor = CorridorService()
        self.corridor.update_frame_size(640, 480)

    def _create_vehicle(self, track_id, cx, cy):
        """Helper to create a tracked vehicle."""
        v = TrackedVehicle(track_id, (cx, cy), [cx-30, cy-30, cx+30, cy+30], "car", 0.9)
        return v

    def test_no_violation_when_emergency_inactive(self):
        """No violation should be generated when emergency is not active."""
        v = self._create_vehicle(1, 320, 350)
        v.update_corridor_status(True)
        v.corridor_enter_time = time.time() - 10  # 10 seconds ago
        v.blocking_time = 10
        v.movement_status = "STOPPED"

        result = self.corridor.check_violation(v, "AMB-2026-0001", emergency_active=False)
        assert result is None

    def test_no_violation_outside_corridor(self):
        """No violation for vehicle outside corridor."""
        v = self._create_vehicle(1, 10, 350)  # Far left, outside corridor
        result = self.corridor.check_violation(v, "AMB-2026-0001", emergency_active=True)
        assert result is None

    def test_no_violation_insufficient_blocking_time(self):
        """No violation if vehicle hasn't been blocking long enough."""
        v = self._create_vehicle(1, 320, 350)  # Center of corridor
        v.in_corridor = True
        v.corridor_enter_time = time.time() - 1  # Only 1 second
        v.blocking_time = 1
        v.movement_status = "STOPPED"

        result = self.corridor.check_violation(v, "AMB-2026-0001", emergency_active=True)
        assert result is None

    def test_no_violation_moving_vehicle(self):
        """No violation if vehicle is moving/clearing."""
        v = self._create_vehicle(1, 320, 350)
        v.in_corridor = True
        v.corridor_enter_time = time.time() - 10
        v.blocking_time = 10
        v.movement_status = "MOVING"

        result = self.corridor.check_violation(v, "AMB-2026-0001", emergency_active=True)
        assert result is None

    def test_violation_confirmed(self):
        """Violation should be confirmed when all conditions met."""
        v = self._create_vehicle(1, 320, 350)
        v.in_corridor = True
        v.corridor_enter_time = time.time() - 5
        v.blocking_time = 5
        v.movement_status = "STOPPED"

        result = self.corridor.check_violation(v, "AMB-2026-0001", emergency_active=True)
        assert result is not None
        assert result["vehicle_tracking_id"] == 1
        assert result["vehicle_type"] == "car"

    def test_low_confidence_rejected(self):
        """Vehicle with low confidence should not generate violation."""
        v = self._create_vehicle(1, 320, 350)
        v.confidence = 0.2  # Below threshold
        v.in_corridor = True
        v.corridor_enter_time = time.time() - 10
        v.blocking_time = 10
        v.movement_status = "STOPPED"

        result = self.corridor.check_violation(v, "AMB-2026-0001", emergency_active=True)
        assert result is None


class TestBlockingTime:
    """Test blocking time calculation."""

    def test_blocking_time_updates(self):
        v = TrackedVehicle(1, (320, 350), [290, 320, 350, 380], "car", 0.9)

        # Enter corridor
        v.update_corridor_status(True)
        time.sleep(0.1)

        # Still in corridor
        v.update_corridor_status(True)
        assert v.blocking_time > 0

    def test_blocking_time_resets_on_exit(self):
        v = TrackedVehicle(1, (320, 350), [290, 320, 350, 380], "car", 0.9)

        v.update_corridor_status(True)
        time.sleep(0.1)
        v.update_corridor_status(True)
        assert v.blocking_time > 0

        # Exit corridor
        v.update_corridor_status(False)
        assert v.blocking_time == 0.0
