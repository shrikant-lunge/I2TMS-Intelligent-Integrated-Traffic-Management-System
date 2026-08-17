"""
Tests for Emergency Service - activation, deactivation, and enforcement restrictions.
"""

import sys
import os
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.emergency_service import EmergencyService
from app.services.gps_service import gps_service


class TestEmergencyActivation:
    """Test emergency start/stop lifecycle."""

    def setup_method(self):
        self.service = EmergencyService()

    def test_initial_state_inactive(self):
        """System should start in INACTIVE state."""
        assert not self.service.is_active
        status = self.service.get_status()
        assert status["status"] == "INACTIVE"

    def test_start_emergency(self):
        """Starting emergency should set mode to ACTIVE."""
        result = self.service.start_emergency(
            destination="AIIMS Nagpur",
            start_lat=21.1458,
            start_lon=79.0882,
            dest_lat=21.1260,
            dest_lon=79.0467,
            route=[],
            junctions=[],
            routing_mode="DEMO",
        )
        assert self.service.is_active
        assert result["status"] == "ACTIVE"
        assert result["event_id"].startswith("AMB-")
        assert result["destination"] == "AIIMS Nagpur"

    def test_stop_emergency(self):
        """Stopping emergency should set mode to COMPLETED."""
        self.service.start_emergency(
            destination="AIIMS Nagpur",
            start_lat=21.1458, start_lon=79.0882,
            dest_lat=21.1260, dest_lon=79.0467,
            route=[], junctions=[], routing_mode="DEMO",
        )
        assert self.service.is_active

        result = self.service.stop_emergency()
        assert not self.service.is_active
        assert result["status"] == "COMPLETED"
        assert "end_time" in result

    def test_stop_when_not_active(self):
        """Stopping when not active should return None."""
        result = self.service.stop_emergency()
        assert result is None

    def test_event_id_generation(self):
        """Event IDs should be unique and sequential."""
        e1 = self.service.start_emergency(
            destination="Test1",
            start_lat=0, start_lon=0,
            dest_lat=0, dest_lon=0,
            route=[], junctions=[], routing_mode="DEMO",
        )
        self.service.stop_emergency()

        e2 = self.service.start_emergency(
            destination="Test2",
            start_lat=0, start_lon=0,
            dest_lat=0, dest_lon=0,
            route=[], junctions=[], routing_mode="DEMO",
        )
        assert e1["event_id"] != e2["event_id"]

    def test_no_enforcement_when_inactive(self):
        """When emergency is not active, is_active should be False."""
        assert not self.service.is_active
        # Enforcement logic depends on this flag


class TestEmergencyEnforcement:
    """Test that enforcement only works during active emergency."""

    def setup_method(self):
        self.service = EmergencyService()

    def test_enforcement_gate_inactive(self):
        """Enforcement must not trigger when emergency is inactive."""
        assert not self.service.is_active
        # This is the gate check used in the pipeline

    def test_enforcement_gate_active(self):
        """Enforcement should be allowed when emergency is active."""
        self.service.start_emergency(
            destination="AIIMS",
            start_lat=0, start_lon=0,
            dest_lat=0, dest_lon=0,
            route=[], junctions=[], routing_mode="DEMO",
        )
        assert self.service.is_active

    def test_enforcement_stops_after_end(self):
        """Enforcement must stop immediately when emergency ends."""
        self.service.start_emergency(
            destination="AIIMS",
            start_lat=0, start_lon=0,
            dest_lat=0, dest_lon=0,
            route=[], junctions=[], routing_mode="DEMO",
        )
        assert self.service.is_active

        self.service.stop_emergency()
        assert not self.service.is_active

    def test_live_position_updates_without_route_simulation(self):
        """The ambulance should not auto-move unless the laptop/device location changes."""
        gps_service.start_simulation([], [], 0.0, 0.0, simulate=False)
        gps_service.set_current_position(12.3456, 78.9012)
        pos = gps_service.get_current_position()
        assert pos["lat"] == 12.3456
        assert pos["lon"] == 78.9012
        assert pos["active"] is False
