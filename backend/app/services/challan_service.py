"""
Challan Service - Simulated e-challan generation.
Clearly labeled as SIMULATED unless a real government API is configured.
"""

import datetime
import logging
from typing import Optional

from sqlalchemy.orm import Session
from app.models.database import ChallanDB, ViolationDB, SessionLocal

logger = logging.getLogger(__name__)

_challan_counter = 0


def generate_challan(violation_id: str) -> Optional[dict]:
    """
    Generate a SIMULATED e-challan for a violation.

    IMPORTANT: This is a prototype. No legally valid government challan
    is issued. The architecture supports future integration with an
    authorized government enforcement API.
    """
    global _challan_counter

    db = SessionLocal()
    try:
        # Find the violation
        violation = (
            db.query(ViolationDB)
            .filter(ViolationDB.violation_id == violation_id)
            .first()
        )

        if violation is None:
            logger.warning(f"Violation not found: {violation_id}")
            return None

        # Check if challan already exists
        existing = (
            db.query(ChallanDB)
            .filter(ChallanDB.violation_id == violation_id)
            .first()
        )
        if existing:
            logger.info(f"Challan already exists for violation: {violation_id}")
            return _challan_to_dict(existing)

        # Generate challan ID
        _challan_counter += 1
        year = datetime.datetime.now().year
        challan_id = f"CH-{year}-{_challan_counter:04d}"

        # Create challan
        challan = ChallanDB(
            challan_id=challan_id,
            violation_id=violation_id,
            emergency_event_id=violation.emergency_event_id,
            vehicle_number=violation.plate_number,
            vehicle_type=violation.vehicle_type,
            violation_type=violation.violation_type,
            timestamp=violation.timestamp,
            location_lat=violation.latitude,
            location_lon=violation.longitude,
            evidence_path=violation.evidence_path,
            confidence_score=violation.plate_confidence,
            status="SIMULATED",
            notes=(
                "SIMULATED E-CHALLAN - This is a prototype challan generated "
                "by the Smart Ambulance Emergency Corridor system. No legally "
                "valid government challan has been issued. This record is for "
                "demonstration purposes only."
            ),
        )

        db.add(challan)

        # Update violation status
        violation.status = "CHALLAN_GENERATED"

        db.commit()
        db.refresh(challan)

        logger.info(f"SIMULATED CHALLAN generated: {challan_id} for violation {violation_id}")
        return _challan_to_dict(challan)

    except Exception as e:
        logger.error(f"Challan generation error: {e}")
        db.rollback()
        return None
    finally:
        db.close()


def get_challan(challan_id: str) -> Optional[dict]:
    """Get a challan by ID."""
    db = SessionLocal()
    try:
        challan = (
            db.query(ChallanDB)
            .filter(ChallanDB.challan_id == challan_id)
            .first()
        )
        if challan:
            return _challan_to_dict(challan)
        return None
    finally:
        db.close()


def get_all_challans() -> list:
    """Get all challans."""
    db = SessionLocal()
    try:
        challans = db.query(ChallanDB).order_by(ChallanDB.created_at.desc()).all()
        return [_challan_to_dict(c) for c in challans]
    finally:
        db.close()


def _challan_to_dict(challan: ChallanDB) -> dict:
    return {
        "challan_id": challan.challan_id,
        "violation_id": challan.violation_id,
        "emergency_event_id": challan.emergency_event_id,
        "vehicle_number": challan.vehicle_number,
        "vehicle_type": challan.vehicle_type,
        "violation_type": challan.violation_type,
        "timestamp": challan.timestamp.isoformat() if challan.timestamp else None,
        "location_lat": challan.location_lat,
        "location_lon": challan.location_lon,
        "evidence_path": challan.evidence_path,
        "confidence_score": challan.confidence_score,
        "status": challan.status,
        "notes": challan.notes,
        "created_at": challan.created_at.isoformat() if challan.created_at else None,
    }
