"""
Tests for Duplicate Violation Prevention.
"""

import sys
import os
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.corridor_service import CorridorService
from app.services.tracking_service import TrackedVehicle


class TestDuplicatePrevention:
    """Test that same vehicle doesn't generate duplicate violations."""

    def setup_method(self):
        self.corridor = CorridorService()
        self.corridor.update_frame_size(640, 480)

    def _create_blocking_vehicle(self, track_id, cx=320, cy=350):
        v = TrackedVehicle(track_id, (cx, cy), [cx-30, cy-30, cx+30, cy+30], "car", 0.9)
        v.in_corridor = True
        v.corridor_enter_time = time.time() - 10
        v.blocking_time = 10
        v.movement_status = "STOPPED"
        return v

    def test_no_duplicate_same_event_same_vehicle(self):
        """Same vehicle + same event should NOT generate duplicate violation."""
        v = self._create_blocking_vehicle(1)

        # First violation - should succeed
        r1 = self.corridor.check_violation(v, "AMB-2026-0001", True)
        assert r1 is not None

        # Second attempt - should be blocked (duplicate)
        r2 = self.corridor.check_violation(v, "AMB-2026-0001", True)
        assert r2 is None

    def test_different_vehicle_same_event_allowed(self):
        """Different vehicle in same event should generate separate violation."""
        v1 = self._create_blocking_vehicle(1)
        v2 = self._create_blocking_vehicle(2)

        r1 = self.corridor.check_violation(v1, "AMB-2026-0001", True)
        r2 = self.corridor.check_violation(v2, "AMB-2026-0001", True)

        assert r1 is not None
        assert r2 is not None

    def test_same_vehicle_different_event_allowed(self):
        """Same vehicle in different event should generate new violation."""
        v = self._create_blocking_vehicle(1)

        r1 = self.corridor.check_violation(v, "AMB-2026-0001", True)
        assert r1 is not None

        # Clear and try with different event
        self.corridor.clear_event_violations("AMB-2026-0001")

        # Need to re-allow this track for new event
        r2 = self.corridor.check_violation(v, "AMB-2026-0002", True)
        assert r2 is not None

    def test_reset_clears_all_violations(self):
        """Reset should clear all violation tracking."""
        v = self._create_blocking_vehicle(1)
        self.corridor.check_violation(v, "AMB-2026-0001", True)

        self.corridor.reset()

        # After reset, same combo should be allowed again
        v2 = self._create_blocking_vehicle(1)
        v2.in_corridor = True
        v2.corridor_enter_time = time.time() - 10
        v2.blocking_time = 10
        v2.movement_status = "STOPPED"

        r = self.corridor.check_violation(v2, "AMB-2026-0001", True)
        assert r is not None
