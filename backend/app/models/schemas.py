"""
Pydantic schemas for API request/response validation.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


# =============================================================================
# Enums
# =============================================================================
class EmergencyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    INACTIVE = "INACTIVE"


class ViolationStatus(str, Enum):
    DETECTED = "DETECTED"
    VERIFIED = "VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CHALLAN_GENERATED = "CHALLAN_GENERATED"
    REJECTED = "REJECTED"


class ChallanStatus(str, Enum):
    SIMULATED = "SIMULATED"
    GENERATED = "GENERATED"
    PENDING_REVIEW = "PENDING_REVIEW"


class MovementStatus(str, Enum):
    MOVING = "MOVING"
    SLOW = "SLOW"
    STOPPED = "STOPPED"
    CLEARING = "CLEARING"


class CameraMode(str, Enum):
    LIVE_CAMERA = "LIVE CAMERA"
    DEMO_VIDEO = "DEMO VIDEO"
    VIDEO_FILE = "VIDEO FILE"
    UNAVAILABLE = "UNAVAILABLE"


class CameraInputMode(str, Enum):
    LIVE_CAMERA = "LIVE_CAMERA"
    VIDEO_FILE = "VIDEO_FILE"


class RoutingMode(str, Enum):
    OSRM = "OSRM"
    DEMO = "DEMO"


# =============================================================================
# Emergency
# =============================================================================
class EmergencyStartRequest(BaseModel):
    destination: str = Field(..., min_length=1, description="Destination name or address")
    current_lat: Optional[float] = Field(None, description="Current latitude")
    current_lon: Optional[float] = Field(None, description="Current longitude")
    ambulance_id: Optional[str] = Field("AMB-DEFAULT-01", description="Ambulance identifier")


class EmergencyStartResponse(BaseModel):
    emergency_event_id: str
    status: EmergencyStatus
    ambulance_id: str
    destination: str
    start_lat: float
    start_lon: float
    dest_lat: float
    dest_lon: float
    routing_mode: RoutingMode
    route: List[List[float]] = []  # [[lon, lat], ...]
    junctions: List[dict] = []
    message: str


class EmergencyStatusResponse(BaseModel):
    emergency_event_id: Optional[str] = None
    status: EmergencyStatus
    ambulance_id: Optional[str] = None
    destination: Optional[str] = None
    start_time: Optional[str] = None
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lon: Optional[float] = None
    routing_mode: Optional[str] = None
    route: List[List[float]] = []
    junctions: List[dict] = []
    next_junction: Optional[dict] = None
    camera_status: Optional[str] = None
    camera_mode: Optional[str] = None
    violations_count: int = 0
    vehicles_detected: int = 0


class EmergencyStopResponse(BaseModel):
    emergency_event_id: str
    status: EmergencyStatus
    end_time: str
    total_violations: int
    message: str


class EmergencyLocationUpdateRequest(BaseModel):
    latitude: float
    longitude: float


# =============================================================================
# Route
# =============================================================================
class RouteCalculateRequest(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float


class RouteResponse(BaseModel):
    routing_mode: RoutingMode
    route: List[List[float]] = []
    distance_km: float = 0.0
    duration_min: float = 0.0
    junctions: List[dict] = []


# =============================================================================
# Vehicles
# =============================================================================
class VehicleInfo(BaseModel):
    tracking_id: int
    vehicle_type: str
    confidence: float
    bbox: List[int]  # [x1, y1, x2, y2]
    center: List[int]  # [cx, cy]
    movement_status: str
    in_corridor: bool
    blocking_time: float = 0.0
    first_seen: Optional[str] = None


# =============================================================================
# Violation
# =============================================================================
class ViolationResponse(BaseModel):
    violation_id: str
    emergency_event_id: str
    vehicle_tracking_id: int
    vehicle_type: Optional[str] = None
    plate_number: Optional[str] = None
    plate_confidence: Optional[float] = None
    detection_confidence: Optional[float] = None
    violation_type: str = "EMERGENCY_CORRIDOR_BLOCKING"
    timestamp: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    evidence_path: Optional[str] = None
    blocking_duration: Optional[float] = None
    movement_status: Optional[str] = None
    status: str


# =============================================================================
# Challan
# =============================================================================
class ChallanGenerateRequest(BaseModel):
    violation_id: str


class ChallanResponse(BaseModel):
    challan_id: str
    violation_id: str
    emergency_event_id: str
    vehicle_number: Optional[str] = None
    vehicle_type: Optional[str] = None
    violation_type: str
    timestamp: str
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    evidence_path: Optional[str] = None
    confidence_score: Optional[float] = None
    status: str
    notes: Optional[str] = None


# =============================================================================
# Camera
# =============================================================================
class CameraStartRequest(BaseModel):
    source: Optional[str] = Field(None, description="Camera index, RTSP URL, or video file path")
    mode: CameraInputMode = CameraInputMode.LIVE_CAMERA


class CameraStatusResponse(BaseModel):
    running: bool
    mode: CameraMode
    source: str
    frame_count: int = 0
    fps: float = 0.0


class PlateRecordResponse(BaseModel):
    id: int
    plate_number: str
    plate_confidence: Optional[float] = None
    source_mode: str
    source_value: Optional[str] = None
    vehicle_type: Optional[str] = None
    status: str
    created_at: Optional[str] = None
