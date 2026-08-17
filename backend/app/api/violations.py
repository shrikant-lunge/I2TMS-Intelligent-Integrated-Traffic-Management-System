"""
Violations API - List and detail violation records.
"""

from fastapi import APIRouter, HTTPException
import logging

from app.models.database import ViolationDB, SessionLocal
from app.models.schemas import ViolationResponse
from app.core.pipeline import pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/violations", tags=["Violations"])


@router.get("")
async def list_violations(emergency_event_id: str = None):
    """List all violations, optionally filtered by emergency event."""
    db = SessionLocal()
    try:
        query = db.query(ViolationDB).order_by(ViolationDB.created_at.desc())
        if emergency_event_id:
            query = query.filter(
                ViolationDB.emergency_event_id == emergency_event_id
            )
        violations = query.all()
        return {
            "violations": [_violation_to_dict(v) for v in violations],
            "count": len(violations),
        }
    finally:
        db.close()


@router.get("/live")
async def live_violations():
    """Get recent violations from the live pipeline (not DB)."""
    return {
        "violations": pipeline.recent_violations,
        "count": len(pipeline.recent_violations),
    }


@router.get("/{violation_id}")
async def get_violation(violation_id: str):
    """Get a specific violation with evidence details."""
    db = SessionLocal()
    try:
        violation = (
            db.query(ViolationDB)
            .filter(ViolationDB.violation_id == violation_id)
            .first()
        )
        if violation is None:
            raise HTTPException(status_code=404, detail="Violation not found")

        result = _violation_to_dict(violation)

        # Add evidence image URLs
        if violation.evidence_path:
            result["evidence_images"] = {
                "full_frame": f"/api/evidence/{violation_id}/full_frame.jpg",
                "vehicle": f"/api/evidence/{violation_id}/vehicle.jpg",
                "plate": f"/api/evidence/{violation_id}/plate.jpg",
            }

        return result
    finally:
        db.close()


def _violation_to_dict(v: ViolationDB) -> dict:
    return {
        "violation_id": v.violation_id,
        "emergency_event_id": v.emergency_event_id,
        "vehicle_tracking_id": v.vehicle_tracking_id,
        "vehicle_type": v.vehicle_type,
        "plate_number": v.plate_number,
        "plate_confidence": v.plate_confidence,
        "detection_confidence": v.detection_confidence,
        "violation_type": v.violation_type,
        "timestamp": v.timestamp.isoformat() if v.timestamp else None,
        "latitude": v.latitude,
        "longitude": v.longitude,
        "evidence_path": v.evidence_path,
        "blocking_duration": v.blocking_duration,
        "movement_status": v.movement_status,
        "status": v.status,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    }
