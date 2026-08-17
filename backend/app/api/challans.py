"""
Challans API - Simulated e-challan generation and retrieval.
"""

from fastapi import APIRouter, HTTPException
import logging

from app.models.schemas import ChallanGenerateRequest, ChallanResponse
from app.services.challan_service import generate_challan, get_challan, get_all_challans

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/challans", tags=["Challans"])


@router.post("/generate")
async def generate(request: ChallanGenerateRequest):
    """
    Generate a SIMULATED e-challan for a violation.

    NOTE: This generates a prototype challan for demonstration purposes.
    No legally valid government challan is issued.
    """
    challan = generate_challan(request.violation_id)
    if challan is None:
        raise HTTPException(
            status_code=404,
            detail="Violation not found or challan generation failed",
        )

    return {
        "message": "SIMULATED E-CHALLAN generated successfully",
        "challan": challan,
    }


@router.get("")
async def list_challans():
    """List all challans."""
    challans = get_all_challans()
    return {
        "challans": challans,
        "count": len(challans),
    }


@router.get("/{challan_id}")
async def get_challan_detail(challan_id: str):
    """Get a specific challan."""
    challan = get_challan(challan_id)
    if challan is None:
        raise HTTPException(status_code=404, detail="Challan not found")
    return challan
