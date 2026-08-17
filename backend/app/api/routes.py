"""
Routes API - Route calculation endpoint.
"""

from fastapi import APIRouter
import logging

from app.models.schemas import RouteCalculateRequest, RouteResponse, RoutingMode
from app.services.routing_service import calculate_route

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/routes", tags=["Routes"])


@router.post("/calculate", response_model=RouteResponse)
async def calc_route(request: RouteCalculateRequest):
    """Calculate a route between two points."""
    result = await calculate_route(
        request.start_lat, request.start_lon,
        request.end_lat, request.end_lon,
    )
    return RouteResponse(
        routing_mode=RoutingMode(result.get("routing_mode", "DEMO")),
        route=result.get("route", []),
        distance_km=result.get("distance_km", 0),
        duration_min=result.get("duration_min", 0),
        junctions=result.get("junctions", []),
    )


@router.get("/current")
async def get_current_route():
    """Get the current active route."""
    from app.services.emergency_service import emergency_service
    from app.services.gps_service import gps_service

    if not emergency_service.is_active:
        return {"active": False, "route": [], "junctions": []}

    gps = gps_service.get_current_position()
    junctions = gps_service.get_junctions()
    next_junction = gps_service.get_next_junction()

    return {
        "active": True,
        "route": emergency_service.route,
        "junctions": junctions,
        "next_junction": next_junction,
        "routing_mode": emergency_service.routing_mode,
        "current_position": gps,
    }
