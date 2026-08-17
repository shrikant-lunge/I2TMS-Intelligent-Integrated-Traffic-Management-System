"""
Tests for Challan Generation.
"""

import sys
import os
import datetime
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.models.database import init_db, SessionLocal, ViolationDB, ChallanDB, Base, engine
from app.services.challan_service import generate_challan, get_challan, get_all_challans


class TestChallanGeneration:
    """Test simulated challan generation."""

    def setup_method(self):
        # Create fresh tables for each test
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        # Create a test violation
        db = SessionLocal()
        violation = ViolationDB(
            violation_id="EV-TEST-0001",
            emergency_event_id="AMB-2026-0001",
            vehicle_tracking_id=1,
            vehicle_type="car",
            plate_number="MH12AB1234",
            plate_confidence=0.85,
            detection_confidence=0.92,
            violation_type="EMERGENCY_CORRIDOR_BLOCKING",
            latitude=21.1458,
            longitude=79.0882,
            evidence_path="data/evidence/EV-TEST-0001",
            status="VERIFIED",
        )
        db.add(violation)
        db.commit()
        db.close()

    def test_generate_challan(self):
        """Challan should be generated for a valid violation."""
        result = generate_challan("EV-TEST-0001")

        assert result is not None
        assert result["challan_id"].startswith("CH-")
        assert result["violation_id"] == "EV-TEST-0001"
        assert result["status"] == "SIMULATED"
        assert result["vehicle_number"] == "MH12AB1234"
        assert "SIMULATED" in result["notes"]

    def test_challan_not_found(self):
        """Challan generation should fail for non-existent violation."""
        result = generate_challan("EV-NONEXISTENT")
        assert result is None

    def test_no_duplicate_challan(self):
        """Same violation should not generate duplicate challan."""
        r1 = generate_challan("EV-TEST-0001")
        r2 = generate_challan("EV-TEST-0001")

        assert r1 is not None
        assert r2 is not None
        assert r1["challan_id"] == r2["challan_id"]  # Same challan returned

    def test_challan_status_simulated(self):
        """Challan status must be SIMULATED."""
        result = generate_challan("EV-TEST-0001")
        assert result["status"] == "SIMULATED"

    def test_violation_status_updated(self):
        """Violation status should be updated to CHALLAN_GENERATED."""
        generate_challan("EV-TEST-0001")

        db = SessionLocal()
        v = db.query(ViolationDB).filter(
            ViolationDB.violation_id == "EV-TEST-0001"
        ).first()
        assert v.status == "CHALLAN_GENERATED"
        db.close()

    def test_get_challan(self):
        """Should be able to retrieve generated challan."""
        generated = generate_challan("EV-TEST-0001")
        retrieved = get_challan(generated["challan_id"])

        assert retrieved is not None
        assert retrieved["challan_id"] == generated["challan_id"]

    def test_list_challans(self):
        """Should be able to list all challans."""
        generate_challan("EV-TEST-0001")
        all_challans = get_all_challans()

        assert len(all_challans) >= 1
