from app.models.user import User
from app.models.junction import Junction
from app.models.alert import Alert
from app.models.signal_plan import SignalPlanHistory
from app.models.emergency import EmergencyRequest
from app.models.vms import VMSBoard
from app.models.report import GeneratedReport
from app.models.settings import SystemSettings
from app.models.violation import Violation
from app.models.challan import Challan
from app.models.route_checkpoint import RouteCheckpoint
from app.models.adaptive_signal_state import AdaptiveSignalState

# ── New Supabase-backed analytics tables ────────────────────────────────
from app.models.traffic_state_snapshot import TrafficStateSnapshot
from app.models.signal_decision import SignalDecision
from app.models.decision_log import DecisionLog
from app.models.traffic_trend import TrafficTrend
from app.models.emergency_corridor_record import EmergencyCorridorRecord
from app.models.emergency_corridor_event import EmergencyCorridorEvent
from app.models.anpr_detection import ANPRDetection
from app.models.emergency_metrics import EmergencyMetrics

# Explicitly export all models so they can be imported from app.models
__all__ = [
    "User",
    "Junction",
    "Alert",
    "SignalPlanHistory",
    "EmergencyRequest",
    "VMSBoard",
    "GeneratedReport",
    "SystemSettings",
    "Violation",
    "Challan",
    "RouteCheckpoint",
    "AdaptiveSignalState",
    # New analytics models
    "TrafficStateSnapshot",
    "SignalDecision",
    "DecisionLog",
    "TrafficTrend",
    "EmergencyCorridorRecord",
    "EmergencyCorridorEvent",
    "ANPRDetection",
    "EmergencyMetrics",
]
