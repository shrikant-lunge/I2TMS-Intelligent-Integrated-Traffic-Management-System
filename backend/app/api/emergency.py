"""
Emergency API - Start/stop emergency events.
"""

from fastapi import APIRouter, HTTPException
import logging

from app.models.schemas import (
    EmergencyStartRequest,
    EmergencyStartResponse,
    EmergencyStatusResponse,
    EmergencyStopResponse,
    EmergencyLocationUpdateRequest,
    EmergencyStatus,
    RoutingMode,
)
from app.services.emergency_service import emergency_service
from app.services.routing_service import calculate_route, geocode_destination, DEFAULT_START
from app.services.gps_service import gps_service
from app.services.corridor_service import corridor_service
from app.services.camera_service import camera_service
from app.core.pipeline import pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/emergency", tags=["Emergency"])


@router.post("/start", response_model=EmergencyStartResponse)
async def start_emergency(request: EmergencyStartRequest):
    """Start a new emergency event."""
    # Resolve coordinates
    start_lat = request.current_lat or DEFAULT_START[0]
    start_lon = request.current_lon or DEFAULT_START[1]

    # Geocode destination
    dest_lat, dest_lon = geocode_destination(request.destination)

    # Calculate route
    route_data = await calculate_route(start_lat, start_lon, dest_lat, dest_lon)

    # Start emergency
    event = emergency_service.start_emergency(
        destination=request.destination,
        start_lat=start_lat,
        start_lon=start_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        route=route_data.get("route", []),
        junctions=route_data.get("junctions", []),
        routing_mode=route_data.get("routing_mode", "DEMO"),
        ambulance_id=request.ambulance_id or "AMB-DEFAULT-01",
    )

    # Start GPS simulation
    gps_service.start_simulation(
        route=route_data.get("route", []),
        junctions=route_data.get("junctions", []),
        start_lat=start_lat,
        start_lon=start_lon,
        simulate=False,
    )

    # Reset corridor violation tracking
    corridor_service.reset()

    # Emergency mode must use the live camera, never a demo video.
    if not camera_service.running:
        camera_service.start(source=0)
    if not pipeline.running:
        pipeline.start()

    logger.info(f"Emergency started: {event['event_id']}")

    return EmergencyStartResponse(
        emergency_event_id=event["event_id"],
        status=EmergencyStatus.ACTIVE,
        ambulance_id=event["ambulance_id"],
        destination=event["destination"],
        start_lat=start_lat,
        start_lon=start_lon,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        routing_mode=RoutingMode(route_data.get("routing_mode", "DEMO")),
        route=route_data.get("route", []),
        junctions=route_data.get("junctions", []),
        message=f"Emergency route activated. Routing mode: {route_data.get('routing_mode', 'DEMO')}",
    )


@router.post("/location")
async def update_location(request: EmergencyLocationUpdateRequest):
    """Update the live ambulance position from the user device location."""
    gps_service.set_current_position(request.latitude, request.longitude)
    return {
        "status": "OK",
        "latitude": request.latitude,
        "longitude": request.longitude,
        "message": "Live location updated",
    }


@router.post("/stop", response_model=EmergencyStopResponse)
async def stop_emergency():
    """Stop the current emergency event."""
    if not emergency_service.is_active:
        raise HTTPException(status_code=400, detail="No active emergency to stop")

    result = emergency_service.stop_emergency()
    if result is None:
        raise HTTPException(status_code=500, detail="Failed to stop emergency")

    # Stop GPS simulation
    gps_service.stop_simulation()

    # Reset corridor
    corridor_service.reset()

    # Reset pipeline state (keep camera running for monitoring)
    pipeline.reset()

    logger.info(f"Emergency stopped: {result['event_id']}")

    return EmergencyStopResponse(
        emergency_event_id=result["event_id"],
        status=EmergencyStatus.COMPLETED,
        end_time=result["end_time"],
        total_violations=result["total_violations"],
        message="Emergency ended. Enforcement stopped. Existing violations preserved.",
    )


@router.get("/status", response_model=EmergencyStatusResponse)
async def get_emergency_status():
    """Get current emergency status."""
    status = emergency_service.get_status()
    gps = gps_service.get_current_position()
    junctions = gps_service.get_junctions()
    next_junction = gps_service.get_next_junction()

    cam_status = camera_service.get_status()

    return EmergencyStatusResponse(
        emergency_event_id=status.get("event_id"),
        status=EmergencyStatus(status.get("status", "INACTIVE")),
        ambulance_id=status.get("ambulance_id"),
        destination=status.get("destination"),
        start_time=status.get("start_time"),
        current_lat=gps.get("lat"),
        current_lon=gps.get("lon"),
        dest_lat=status.get("dest_lat"),
        dest_lon=status.get("dest_lon"),
        routing_mode=status.get("routing_mode"),
        route=emergency_service.route,
        junctions=junctions,
        next_junction=next_junction,
        camera_status="RUNNING" if cam_status["running"] else "STOPPED",
        camera_mode=cam_status["mode"],
        violations_count=len(pipeline.recent_violations),
        vehicles_detected=len(pipeline.current_vehicles),
    )
