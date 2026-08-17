"""
Emergency Corridor Service
==========================
In-memory state machine for the active emergency green corridor.

Lifecycle:
  IDLE → ROUTE_CALCULATING → ROUTE_READY → EMERGENCY_STARTED
       → (per junction) APPROACHING_JUNCTION → SIGNAL_PRIORITY_ACTIVE → JUNCTION_PASSED
       → (per VMS)      APPROACHING_VMS      → VMS_CLEAR_LANE_ACTIVE  → VMS_PASSED
       → HOSPITAL_REACHED → CORRIDOR_COMPLETED → IDLE

DB persistence is handled by helper methods that acquire a Flask app context
so the background simulation thread can safely write to SQLAlchemy.
"""

from __future__ import annotations

import json
import logging
import math
import random
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
_BASE = Path(__file__).resolve().parent.parent.parent  # project root  (I2TMS/)
_EMERGENCY_DATA = _BASE / "data" / "emergency"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Haversine distance (km)
# ---------------------------------------------------------------------------
def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DIRECTIONS = ("north", "east", "south", "west")
DEFAULT_VMS_MESSAGE = "DRIVE CAUTIOUSLY\nHAVE A GOOD DAY"
EMERGENCY_VMS_MESSAGE = "CLEAR THE RIGHT LANE\nEMERGENCY VEHICLE APPROACHING"


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return compass bearing (0–360°) from point 1 → point 2."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360


def _bearing_to_approach(bearing_deg: float) -> str:
    """Convert a bearing (direction of travel) to the cardinal approach label."""
    if 45 <= bearing_deg < 135:
        return "east"
    elif 135 <= bearing_deg < 225:
        return "south"
    elif 225 <= bearing_deg < 315:
        return "west"
    else:
        return "north"


def _build_junction_state(j: dict, prev_lat: float = 0.0, prev_lon: float = 0.0) -> dict:
    approach = j.get("ambulance_approach", "").strip()
    if not approach or approach not in DIRECTIONS:
        if prev_lat != 0.0 or prev_lon != 0.0:
            b = _bearing(prev_lat, prev_lon, j["lat"], j["lon"])
            approach = _bearing_to_approach(b)
        else:
            approach = "north"

    signals = {d: ("green" if d == approach else "red") for d in DIRECTIONS}

    return {
        "id": j["id"],
        "name": j["name"],
        "lat": j["lat"],
        "lon": j["lon"],
        "sequence": j["sequence"],
        "ambulance_approach": approach,
        "phase": "normal",
        "emergency_signals": signals,
        "status": "pending",
    }


def _build_vms_state(v: dict) -> dict:
    return {
        "id": v["id"],
        "name": v["name"],
        "lat": v["lat"],
        "lon": v["lon"],
        "sequence": v["sequence"],
        "status": "normal",
        "message": DEFAULT_VMS_MESSAGE,
    }


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------
class EmergencyCorridorService:
    """
    Singleton in-memory state machine for the active Emergency Green Corridor.
    Thread-safe: every public method acquires self._lock.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._reset_state()
        self._flask_app = None   # set by init_app() after app factory runs

        # Load global config once
        try:
            cfg = _load_json(_EMERGENCY_DATA / "routes.json")
            self._vms_trigger_km: float = cfg.get("vms_trigger_distance_km", 1.5)
            self._junction_trigger_km: float = cfg.get("junction_trigger_distance_km", 0.3)
            self._junction_passed_km: float = cfg.get("junction_passed_distance_km", 0.05)
            self._speed_min: int = cfg.get("simulation_speed_kmh_min", 40)
            self._speed_max: int = cfg.get("simulation_speed_kmh_max", 60)
            self._anpr_trigger_seq: int = cfg.get("anpr_trigger", {}).get("sequence", 1)
            self._destinations: List[dict] = cfg.get("destinations", [])
        except Exception as exc:
            logger.warning("Could not load routes.json: %s", exc)
            self._vms_trigger_km = 1.5
            self._junction_trigger_km = 0.3
            self._junction_passed_km = 0.05
            self._speed_min = 40
            self._speed_max = 60
            self._anpr_trigger_seq = 1
            self._destinations = []

        # Pre-load ANPR detections
        try:
            anpr_data = _load_json(_EMERGENCY_DATA / "anpr_detections.json")
            self._anpr_detections: List[dict] = anpr_data.get("detections", [])
        except Exception as exc:
            logger.warning("Could not load anpr_detections.json: %s", exc)
            self._anpr_detections = []

    # ------------------------------------------------------------------
    # Flask app context bridge
    # ------------------------------------------------------------------
    def init_app(self, app) -> None:
        """Register the Flask app so background threads can use app context."""
        self._flask_app = app

    def _db_write(self, fn) -> None:
        """
        Execute fn(db) inside a Flask app context.
        Safe to call from the background simulation thread.
        Failures are logged but never raised so the sim loop never crashes.
        """
        if self._flask_app is None:
            return
        try:
            with self._flask_app.app_context():
                from app.extensions import db
                fn(db)
                db.session.commit()
        except Exception as exc:
            logger.warning("[corridor-db] write failed: %s", exc)

    # ------------------------------------------------------------------
    # Internal reset
    # ------------------------------------------------------------------
    def _reset_state(self):
        self.corridor_id: Optional[str] = None
        self.state: str = "IDLE"

        self.route_id: Optional[str] = None
        self.route_geometry: List[list] = []
        self.distance_km: float = 0.0
        self.baseline_duration_min: float = 0.0
        self.optimized_duration_min: float = 0.0
        self.source: dict = {}
        self.destination_info: dict = {}

        self._route_index: int = 0
        self._paused: bool = False
        self._sim_thread: Optional[threading.Thread] = None
        self._sim_running: bool = False
        self.ambulance_lat: float = 0.0
        self.ambulance_lon: float = 0.0
        self.current_speed_kmh: int = 0
        self.route_progress_pct: float = 0.0
        self.distance_remaining_km: float = 0.0
        self.eta_minutes: float = 0.0
        self.started_at: Optional[str] = None

        self.junctions: List[dict] = []
        self.vms_boards: List[dict] = []

        self.current_junction_name: Optional[str] = None
        self.next_junction_name: Optional[str] = None
        self.next_junction_distance_km: Optional[float] = None
        self.current_vms_message: str = DEFAULT_VMS_MESSAGE
        self.signal_phase: str = "normal"

        self.junctions_prioritised: int = 0
        self.vms_activated: int = 0
        self.anpr_detection_count: int = 0

        self._anpr_started: bool = False
        self._anpr_start_time: Optional[float] = None
        self.anpr_history: List[dict] = []
        self._anpr_emitted_indices: set = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_destinations(self) -> List[dict]:
        return deepcopy(self._destinations)

    def calculate_route(self, destination_id: str, osrm_result: dict) -> dict:
        with self._lock:
            dest_meta = next(
                (d for d in self._destinations if d["id"] == destination_id), None
            )
            if dest_meta is None:
                raise ValueError(f"Unknown destination_id: {destination_id!r}")

            route_id = dest_meta["route_id"]

            infra_path = _EMERGENCY_DATA / f"{route_id}.json"
            try:
                infra = _load_json(infra_path)
            except FileNotFoundError:
                raise ValueError(f"Infrastructure file not found: {infra_path}")

            geometry = osrm_result.get("route", [])
            distance_km = float(osrm_result.get("distance_km", 0.0))
            osrm_duration_min = float(osrm_result.get("duration_min", 0.0))
            baseline_min = infra.get("baseline_time_minutes") or round(osrm_duration_min, 1)
            optimized_min = infra.get("prototype_optimized_time_minutes") or round(baseline_min * 0.5, 1)

            self.state = "ROUTE_READY"
            self.route_id = route_id
            self.route_geometry = geometry
            self.distance_km = distance_km
            self.baseline_duration_min = baseline_min
            self.optimized_duration_min = optimized_min
            self.source = infra.get("source", {})
            self.destination_info = infra.get("destination", {})
            self.distance_remaining_km = distance_km
            self.eta_minutes = optimized_min

            infra_src = infra.get("source", {})
            prev_lat = float(infra_src.get("lat", 0.0))
            prev_lon = float(infra_src.get("lon", 0.0))
            self.junctions = []
            for j in infra.get("junctions", []):
                state = _build_junction_state(j, prev_lat, prev_lon)
                self.junctions.append(state)
                prev_lat = j["lat"]
                prev_lon = j["lon"]
            self.vms_boards = [_build_vms_state(v) for v in infra.get("vms", [])]

            src = infra.get("source", {})
            self.ambulance_lat = float(src.get("lat", 21.123028))
            self.ambulance_lon = float(src.get("lon", 79.051449))

            logger.info("Route calculated: %s  %.2f km  baseline=%s min  optimized=%s min",
                        route_id, distance_km, baseline_min, optimized_min)

            return {
                "route_id": route_id,
                "source": self.source,
                "destination": self.destination_info,
                "distance_km": distance_km,
                "baseline_duration_minutes": baseline_min,
                "optimized_duration_minutes": optimized_min,
                "geometry": geometry,
                "junctions": [{"id": j["id"], "name": j["name"],
                                "lat": j["lat"], "lon": j["lon"],
                                "sequence": j["sequence"]} for j in self.junctions],
                "vms": [{"id": v["id"], "name": v["name"],
                         "lat": v["lat"], "lon": v["lon"],
                         "sequence": v["sequence"]} for v in self.vms_boards],
            }

    def start(self, route_id: str) -> dict:
        with self._lock:
            if self.state not in ("ROUTE_READY", "IDLE"):
                raise RuntimeError(f"Cannot start in state {self.state!r}")
            if self.route_id != route_id:
                raise RuntimeError("route_id mismatch — call /api/emergency/route first")

            self.corridor_id = str(uuid.uuid4())[:8].upper()
            self.state = "EMERGENCY_STARTED"
            self._paused = False
            self._route_index = 0
            self.started_at = datetime.now(timezone.utc).isoformat()
            self.current_speed_kmh = random.randint(self._speed_min, self._speed_max)

            self._anpr_started = False
            self._anpr_start_time = None
            self.anpr_history = []
            self._anpr_emitted_indices = set()

            self.junctions_prioritised = 0
            self.vms_activated = 0
            self.anpr_detection_count = 0

            # Snapshot for DB write (released before acquiring lock in thread)
            corridor_id    = self.corridor_id
            source         = deepcopy(self.source)
            destination    = deepcopy(self.destination_info)
            distance_km    = self.distance_km
            baseline_min   = self.baseline_duration_min
            optimized_min  = self.optimized_duration_min
            route_id_snap  = self.route_id
            started_at_str = self.started_at

            self._sim_running = True
            self._sim_thread = threading.Thread(
                target=self._simulation_loop, daemon=True, name="corridor-sim"
            )
            self._sim_thread.start()

            logger.info("Emergency corridor STARTED: id=%s route=%s", corridor_id, route_id)

        # ── Persist corridor record ──────────────────────────────────────────
        def _create_corridor(db):
            from app.models.emergency_corridor_record import EmergencyCorridorRecord
            from app.models.emergency_corridor_event import EmergencyCorridorEvent

            started_dt = datetime.fromisoformat(started_at_str.replace("Z", "+00:00")).replace(tzinfo=None)

            rec = EmergencyCorridorRecord(
                corridor_id          = corridor_id,
                source_name          = source.get("name", "VNIT Nagpur"),
                source_lat           = source.get("lat"),
                source_lon           = source.get("lon"),
                destination_name     = destination.get("name", "Hospital"),
                destination_lat      = destination.get("lat"),
                destination_lon      = destination.get("lon"),
                route_id             = route_id_snap,
                distance_km          = distance_km,
                baseline_eta_minutes = baseline_min,
                optimized_eta_minutes = optimized_min,
                time_saved_minutes   = round(baseline_min - optimized_min, 1),
                status               = "ACTIVE",
                started_at           = started_dt,
                created_at           = started_dt,
            )
            db.session.add(rec)
            db.session.flush()

            event = EmergencyCorridorEvent(
                corridor_id = corridor_id,
                event_type  = "CORRIDOR_STARTED",
                latitude    = source.get("lat"),
                longitude   = source.get("lon"),
                description = f"Emergency corridor started: {source.get('name')} → {destination.get('name')}",
                event_data  = {
                    "distance_km": distance_km,
                    "baseline_eta_minutes": baseline_min,
                    "optimized_eta_minutes": optimized_min,
                },
                created_at  = started_dt,
            )
            db.session.add(event)

        self._db_write(_create_corridor)

        return {"corridor_id": self.corridor_id, "status": "ACTIVE"}

    def pause(self) -> dict:
        with self._lock:
            self._paused = True
            self.current_speed_kmh = 0
            logger.info("Corridor PAUSED")
            return {"status": "PAUSED"}

    def resume(self) -> dict:
        with self._lock:
            self._paused = False
            self.current_speed_kmh = random.randint(self._speed_min, self._speed_max)
            logger.info("Corridor RESUMED")
            return {"status": "ACTIVE"}

    def reset(self) -> dict:
        with self._lock:
            corridor_id = self.corridor_id
            self._sim_running = False
            self._paused = False
        if self._sim_thread and self._sim_thread.is_alive():
            self._sim_thread.join(timeout=3.0)

        # Mark corridor CLOSED in DB
        if corridor_id:
            def _close_corridor(db):
                from app.models.emergency_corridor_record import EmergencyCorridorRecord
                from app.models.emergency_corridor_event import EmergencyCorridorEvent
                rec = EmergencyCorridorRecord.query.filter_by(corridor_id=corridor_id).first()
                if rec and rec.status == "ACTIVE":
                    rec.status = "CLOSED"
                    rec.completed_at = datetime.utcnow()
                    db.session.add(EmergencyCorridorEvent(
                        corridor_id = corridor_id,
                        event_type  = "CORRIDOR_CLOSED",
                        description = "Corridor reset/closed by operator",
                        created_at  = datetime.utcnow(),
                    ))
            self._db_write(_close_corridor)

        with self._lock:
            self._reset_state()
            logger.info("Corridor RESET to IDLE")
            return {"status": "IDLE"}

    def get_status(self) -> dict:
        with self._lock:
            current_j = next((j for j in self.junctions if j["status"] == "active"), None)
            next_j    = next((j for j in self.junctions if j["status"] == "pending"), None)

            active_vms_msg  = DEFAULT_VMS_MESSAGE
            active_vms_name = None
            for v in self.vms_boards:
                if v["status"] == "emergency_warning":
                    active_vms_msg  = EMERGENCY_VMS_MESSAGE
                    active_vms_name = v["name"]
                    break

            sig_colour = "green" if self.signal_phase == "emergency_green" else "normal"

            return {
                "corridor_id": self.corridor_id,
                "state":       self.state,
                "paused":      self._paused,
                "route_id":    self.route_id,
                "ambulance": {
                    "lat":                   self.ambulance_lat,
                    "lon":                   self.ambulance_lon,
                    "speed_kmh":             self.current_speed_kmh,
                    "route_progress_pct":    round(self.route_progress_pct, 2),
                    "distance_remaining_km": round(self.distance_remaining_km, 2),
                    "eta_minutes":           round(self.eta_minutes, 1),
                },
                "current_junction": current_j["name"] if current_j else None,
                "next_junction":    next_j["name"]    if next_j    else None,
                "next_junction_distance_km": round(
                    _haversine(self.ambulance_lat, self.ambulance_lon,
                               next_j["lat"], next_j["lon"]), 2
                ) if next_j and next_j["lat"] != 0.0 else None,
                "signal_phase":              sig_colour,
                "current_junction_signals":  current_j["emergency_signals"] if current_j else None,
                "current_vms_message":       active_vms_msg,
                "active_vms_name":           active_vms_name,
                "junctions":                 deepcopy(self.junctions),
                "vms_boards":                deepcopy(self.vms_boards),
                "anpr": {
                    "started": self._anpr_started,
                    "history": list(reversed(self.anpr_history)),
                },
                "stats": {
                    "junctions_prioritised":      self.junctions_prioritised,
                    "vms_activated":              self.vms_activated,
                    "anpr_detections":            self.anpr_detection_count,
                    "baseline_duration_minutes":  self.baseline_duration_min,
                    "optimized_duration_minutes": self.optimized_duration_min,
                    "time_saved_minutes": round(
                        self.baseline_duration_min - self.optimized_duration_min, 1
                    ),
                },
                "source":      self.source,
                "destination": self.destination_info,
                "distance_km": self.distance_km,
                "started_at":  self.started_at,
            }

    # ------------------------------------------------------------------
    # Background simulation loop
    # ------------------------------------------------------------------
    def _simulation_loop(self):
        TICK = 0.5

        while self._sim_running:
            time.sleep(TICK)

            with self._lock:
                if self._paused or not self._sim_running:
                    continue

                coords = self.route_geometry
                if not coords:
                    self._finish_corridor()
                    break

                total_points = len(coords)

                if total_points > 1:
                    total_route_m = self.distance_km * 1000.0
                    metres_per_wp = total_route_m / max(total_points - 1, 1)
                    speed_mps = self.current_speed_kmh * 1000.0 / 3600.0
                    steps = max(1, round((speed_mps * TICK) / max(metres_per_wp, 1.0)))
                else:
                    steps = 1

                self._route_index = min(self._route_index + steps, total_points - 1)
                point = coords[self._route_index]
                self.ambulance_lon = point[0]
                self.ambulance_lat = point[1]

                self.route_progress_pct = (self._route_index / max(total_points - 1, 1)) * 100.0
                self.distance_remaining_km = self.distance_km * (1.0 - self.route_progress_pct / 100.0)

                avg_speed_kmh = max(self.current_speed_kmh, 20)
                self.eta_minutes = (self.distance_remaining_km / avg_speed_kmh) * 60.0

                if random.random() < 0.15:
                    self.current_speed_kmh = random.randint(self._speed_min, self._speed_max)

                self._update_junctions()
                self._update_vms()
                self._update_anpr()

                if self._route_index >= total_points - 1:
                    self._finish_corridor()
                    break

    # ------------------------------------------------------------------
    # Junction FSM
    # ------------------------------------------------------------------
    def _update_junctions(self):
        for j in self.junctions:
            if j["status"] == "passed":
                continue

            if j["lat"] == 0.0 and j["lon"] == 0.0:
                self._simulate_junction_by_progress(j)
                continue

            dist = _haversine(self.ambulance_lat, self.ambulance_lon, j["lat"], j["lon"])

            if j["status"] == "pending" and dist <= self._junction_trigger_km:
                j["status"] = "active"
                self.signal_phase = "emergency_green"
                self.junctions_prioritised += 1
                # Snapshot for thread-safe DB write
                _cid = self.corridor_id
                _jname = j["name"]
                _lat = j["lat"]
                _lon = j["lon"]
                _signals = deepcopy(j["emergency_signals"])

                def _write_junction_active(db, cid=_cid, jname=_jname, lat=_lat, lon=_lon, sigs=_signals):
                    from app.models.emergency_corridor_event import EmergencyCorridorEvent
                    db.session.add(EmergencyCorridorEvent(
                        corridor_id = cid,
                        event_type  = "SIGNAL_PRIORITY_ACTIVATED",
                        latitude    = lat,
                        longitude   = lon,
                        description = f"Signal priority activated at {jname}",
                        event_data  = {"junction": jname, "signals": sigs},
                        created_at  = datetime.utcnow(),
                    ))
                self._db_write(_write_junction_active)
                logger.debug("Junction ACTIVE: %s (%.3f km)", j["name"], dist)

            elif j["status"] == "active" and dist <= self._junction_passed_km:
                j["status"] = "passed"
                j["phase"] = "passed"
                self.signal_phase = "normal"
                if not self._anpr_started and j["sequence"] == self._anpr_trigger_seq:
                    self._anpr_started = True
                    self._anpr_start_time = time.time()
                    logger.info("ANPR demo triggered after junction: %s", j["name"])

                _cid = self.corridor_id
                _jname = j["name"]
                _lat = j["lat"]
                _lon = j["lon"]

                def _write_junction_passed(db, cid=_cid, jname=_jname, lat=_lat, lon=_lon):
                    from app.models.emergency_corridor_event import EmergencyCorridorEvent
                    db.session.add(EmergencyCorridorEvent(
                        corridor_id = cid,
                        event_type  = "JUNCTION_PASSED",
                        latitude    = lat,
                        longitude   = lon,
                        description = f"Ambulance passed junction {jname}",
                        event_data  = {"junction": jname},
                        created_at  = datetime.utcnow(),
                    ))
                self._db_write(_write_junction_passed)
                logger.debug("Junction PASSED: %s", j["name"])

    def _simulate_junction_by_progress(self, j: dict):
        total = len(self.junctions)
        trigger_pct = (j["sequence"] - 0.7) / total * 100.0
        passed_pct  = (j["sequence"] - 0.1) / total * 100.0

        if j["status"] == "pending" and self.route_progress_pct >= trigger_pct:
            j["status"] = "active"
            self.signal_phase = "emergency_green"
            self.junctions_prioritised += 1

        elif j["status"] == "active" and self.route_progress_pct >= passed_pct:
            j["status"] = "passed"
            j["phase"] = "passed"
            self.signal_phase = "normal"
            if not self._anpr_started and j["sequence"] == self._anpr_trigger_seq:
                self._anpr_started = True
                self._anpr_start_time = time.time()

    # ------------------------------------------------------------------
    # VMS FSM
    # ------------------------------------------------------------------
    def _update_vms(self):
        for v in self.vms_boards:
            if v["status"] == "passed":
                continue

            if v["lat"] == 0.0 and v["lon"] == 0.0:
                self._simulate_vms_by_progress(v)
                continue

            dist = _haversine(self.ambulance_lat, self.ambulance_lon, v["lat"], v["lon"])

            if v["status"] == "normal" and dist <= self._vms_trigger_km:
                v["status"] = "emergency_warning"
                v["message"] = EMERGENCY_VMS_MESSAGE
                self.vms_activated += 1

                _cid = self.corridor_id
                _vname = v["name"]
                _vid = v["id"]
                _lat = v["lat"]
                _lon = v["lon"]

                def _write_vms_active(db, cid=_cid, vname=_vname, vid=_vid, lat=_lat, lon=_lon):
                    from app.models.emergency_corridor_event import EmergencyCorridorEvent
                    db.session.add(EmergencyCorridorEvent(
                        corridor_id = cid,
                        event_type  = "VMS_WARNING_ACTIVATED",
                        vms_id      = vid,
                        latitude    = lat,
                        longitude   = lon,
                        description = f"VMS '{vname}' set to CLEAR LANE warning",
                        event_data  = {"vms_id": vid, "message": EMERGENCY_VMS_MESSAGE},
                        created_at  = datetime.utcnow(),
                    ))
                self._db_write(_write_vms_active)
                logger.debug("VMS EMERGENCY: %s (%.3f km)", v["name"], dist)

            elif v["status"] == "emergency_warning":
                total = len(self.vms_boards)
                passed_pct = (v["sequence"] / (total + 1)) * 100.0
                if self.route_progress_pct >= passed_pct + 5.0:
                    v["status"] = "passed"
                    v["message"] = DEFAULT_VMS_MESSAGE

                    _cid = self.corridor_id
                    _vid = v["id"]
                    _vname = v["name"]

                    def _write_vms_passed(db, cid=_cid, vid=_vid, vname=_vname):
                        from app.models.emergency_corridor_event import EmergencyCorridorEvent
                        db.session.add(EmergencyCorridorEvent(
                            corridor_id = cid,
                            event_type  = "VMS_PASSED",
                            vms_id      = vid,
                            description = f"Ambulance passed VMS '{vname}'",
                            created_at  = datetime.utcnow(),
                        ))
                    self._db_write(_write_vms_passed)
                    logger.debug("VMS PASSED: %s", v["name"])

    def _simulate_vms_by_progress(self, v: dict):
        total = len(self.vms_boards)
        trigger_pct = ((v["sequence"] - 1) / max(total, 1)) * 100.0
        passed_pct  = (v["sequence"] / max(total, 1)) * 100.0

        if v["status"] == "normal" and self.route_progress_pct >= trigger_pct:
            v["status"] = "emergency_warning"
            v["message"] = EMERGENCY_VMS_MESSAGE
            self.vms_activated += 1

        elif v["status"] == "emergency_warning" and self.route_progress_pct >= passed_pct:
            v["status"] = "passed"
            v["message"] = DEFAULT_VMS_MESSAGE

    # ------------------------------------------------------------------
    # ANPR log emitter
    # ------------------------------------------------------------------
    def _update_anpr(self):
        if not self._anpr_started or self._anpr_start_time is None:
            return

        elapsed = time.time() - self._anpr_start_time

        for idx, det in enumerate(self._anpr_detections):
            if idx in self._anpr_emitted_indices:
                continue
            if elapsed >= det["timestamp_sec"]:
                self._anpr_emitted_indices.add(idx)
                self.anpr_detection_count += 1
                entry = {
                    "log_time":      datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "plate":         det["plate"],
                    "confidence":    det["confidence"],
                    "is_primary":    det.get("is_primary", False),
                    "car_id":        det["car_id"],
                    "source":        det.get("source", "Ambulance CCTV"),
                    "frame":         det["frame_number"],
                    "timestamp_sec": det["timestamp_sec"],
                }
                self.anpr_history.append(entry)

                # Persist to DB
                _cid  = self.corridor_id
                _det  = dict(det)
                _now  = datetime.utcnow()
                _alat = self.ambulance_lat
                _alon = self.ambulance_lon

                def _write_anpr(db, cid=_cid, d=_det, ts=_now, lat=_alat, lon=_alon):
                    from app.models.anpr_detection import ANPRDetection
                    from app.models.emergency_corridor_event import EmergencyCorridorEvent
                    det_row = ANPRDetection(
                        corridor_id         = cid,
                        plate_number        = d["plate"],
                        confidence          = d["confidence"],
                        is_primary          = d.get("is_primary", False),
                        car_id              = d["car_id"],
                        latitude            = lat,
                        longitude           = lon,
                        checkpoint_name     = "Ambulance CCTV",
                        detected_at         = ts,
                        video_timestamp_sec = d["timestamp_sec"],
                        source              = d.get("source", "Ambulance CCTV"),
                    )
                    db.session.add(det_row)
                    db.session.add(EmergencyCorridorEvent(
                        corridor_id = cid,
                        event_type  = "ANPR_DETECTED",
                        latitude    = lat,
                        longitude   = lon,
                        description = f"ANPR: {d['plate']} (conf {d['confidence']:.2f})",
                        event_data  = {
                            "plate":         d["plate"],
                            "confidence":    d["confidence"],
                            "is_primary":    d.get("is_primary", False),
                            "car_id":        d["car_id"],
                            "timestamp_sec": d["timestamp_sec"],
                        },
                        created_at  = ts,
                    ))
                self._db_write(_write_anpr)
                logger.debug("ANPR emit: %s (%.3f conf) at t=%.2fs",
                             det["plate"], det["confidence"], elapsed)

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------
    def _finish_corridor(self):
        self._sim_running = False
        self.state = "CORRIDOR_COMPLETED"
        self.route_progress_pct = 100.0
        self.distance_remaining_km = 0.0
        self.eta_minutes = 0.0
        self.current_speed_kmh = 0
        self.signal_phase = "normal"
        for v in self.vms_boards:
            v["message"] = DEFAULT_VMS_MESSAGE

        junctions_prioritised = self.junctions_prioritised
        vms_activated         = self.vms_activated
        anpr_count            = self.anpr_detection_count
        baseline_min          = self.baseline_duration_min
        optimized_min         = self.optimized_duration_min
        corridor_id           = self.corridor_id
        dest                  = deepcopy(self.destination_info)
        started_at_str        = self.started_at

        logger.info(
            "Corridor COMPLETED: junctions=%d vms=%d anpr=%d",
            junctions_prioritised, vms_activated, anpr_count,
        )

        def _write_completion(db, cid=corridor_id, junc=junctions_prioritised,
                              vms=vms_activated, anpr=anpr_count,
                              base=baseline_min, opt=optimized_min,
                              dest_info=dest, started=started_at_str):
            from app.models.emergency_corridor_record import EmergencyCorridorRecord
            from app.models.emergency_corridor_event import EmergencyCorridorEvent
            from app.models.emergency_metrics import EmergencyMetrics

            now = datetime.utcnow()

            rec = EmergencyCorridorRecord.query.filter_by(corridor_id=cid).first()
            if rec:
                rec.status       = "COMPLETED"
                rec.completed_at = now

            db.session.add(EmergencyCorridorEvent(
                corridor_id = cid,
                event_type  = "HOSPITAL_REACHED",
                latitude    = dest_info.get("lat"),
                longitude   = dest_info.get("lon"),
                description = f"Ambulance reached {dest_info.get('name', 'destination')}",
                event_data  = {"destination": dest_info.get("name")},
                created_at  = now,
            ))

            # Parse started_at
            departure_time = None
            if started:
                try:
                    departure_time = datetime.fromisoformat(started.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    pass

            actual_eta = (now - departure_time).total_seconds() / 60.0 if departure_time else opt

            existing_metrics = EmergencyMetrics.query.filter_by(corridor_id=cid).first()
            if existing_metrics is None:
                db.session.add(EmergencyMetrics(
                    corridor_id                     = cid,
                    departure_time                  = departure_time,
                    arrival_time                    = now,
                    baseline_eta_minutes            = base,
                    actual_or_simulated_eta_minutes = round(actual_eta, 1),
                    time_saved_minutes              = round(base - actual_eta, 1),
                    junctions_crossed               = junc,
                    signals_prioritized             = junc,
                    vms_activated                   = vms,
                    anpr_detections                 = anpr,
                    total_vms_events                = vms,
                    created_at                      = now,
                ))

        self._db_write(_write_completion)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
corridor_service = EmergencyCorridorService()

from __future__ import annotations

import json
import logging
import math
import random
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------
_BASE = Path(__file__).resolve().parent.parent.parent  # project root  (I2TMS/)
_EMERGENCY_DATA = _BASE / "data" / "emergency"


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Haversine distance (km)
# ---------------------------------------------------------------------------
def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DIRECTIONS = ("north", "east", "south", "west")
DEFAULT_VMS_MESSAGE = "DRIVE CAUTIOUSLY\nHAVE A GOOD DAY"
EMERGENCY_VMS_MESSAGE = "CLEAR THE RIGHT LANE\nEMERGENCY VEHICLE APPROACHING"


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return compass bearing (0–360°) from point 1 → point 2."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360


def _bearing_to_approach(bearing_deg: float) -> str:
    """Convert a bearing (direction of travel) to the cardinal approach label."""
    if 45 <= bearing_deg < 135:
        return "east"
    elif 135 <= bearing_deg < 225:
        return "south"
    elif 225 <= bearing_deg < 315:
        return "west"
    else:
        return "north"


def _build_junction_state(j: dict, prev_lat: float = 0.0, prev_lon: float = 0.0) -> dict:
    """
    Initialise a junction state dict from route-data entry.

    ambulance_approach is taken from the JSON if present and non-empty.
    If absent/empty, it is computed from the bearing between the previous
    point (source or previous junction) and this junction — so manual entry
    is never required.
    """
    # Auto-compute approach from bearing when not manually provided
    approach = j.get("ambulance_approach", "").strip()
    if not approach or approach not in DIRECTIONS:
        if prev_lat != 0.0 or prev_lon != 0.0:
            b = _bearing(prev_lat, prev_lon, j["lat"], j["lon"])
            approach = _bearing_to_approach(b)
        else:
            approach = "north"  # safe fallback

    signals = {d: ("green" if d == approach else "red") for d in DIRECTIONS}

    return {
        "id": j["id"],
        "name": j["name"],
        "lat": j["lat"],
        "lon": j["lon"],
        "sequence": j["sequence"],
        "ambulance_approach": approach,
        "phase": "normal",
        "emergency_signals": signals,
        "status": "pending",
    }


def _build_vms_state(v: dict) -> dict:
    """Initialise a VMS state dict from route-data entry."""
    return {
        "id": v["id"],
        "name": v["name"],
        "lat": v["lat"],
        "lon": v["lon"],
        "sequence": v["sequence"],
        # lifecycle: normal | emergency_warning | passed
        "status": "normal",
        "message": DEFAULT_VMS_MESSAGE,
    }


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------
class EmergencyCorridorService:
    """
    Singleton in-memory state machine for the active Emergency Green Corridor.

    Thread-safe: every public method acquires self._lock.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._reset_state()

        # Load global config once
        try:
            cfg = _load_json(_EMERGENCY_DATA / "routes.json")
            self._vms_trigger_km: float = cfg.get("vms_trigger_distance_km", 1.5)
            self._junction_trigger_km: float = cfg.get("junction_trigger_distance_km", 0.3)
            self._junction_passed_km: float = cfg.get("junction_passed_distance_km", 0.05)
            self._speed_min: int = cfg.get("simulation_speed_kmh_min", 40)
            self._speed_max: int = cfg.get("simulation_speed_kmh_max", 60)
            self._anpr_trigger_seq: int = cfg.get("anpr_trigger", {}).get("sequence", 1)
            self._destinations: List[dict] = cfg.get("destinations", [])
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not load routes.json: %s", exc)
            self._vms_trigger_km = 1.5
            self._junction_trigger_km = 0.3
            self._junction_passed_km = 0.05
            self._speed_min = 40
            self._speed_max = 60
            self._anpr_trigger_seq = 1
            self._destinations = []

        # Pre-load ANPR detections
        try:
            anpr_data = _load_json(_EMERGENCY_DATA / "anpr_detections.json")
            self._anpr_detections: List[dict] = anpr_data.get("detections", [])
        except Exception as exc:
            logger.warning("Could not load anpr_detections.json: %s", exc)
            self._anpr_detections = []

    # ------------------------------------------------------------------
    # Internal reset
    # ------------------------------------------------------------------
    def _reset_state(self):
        """Reset all mutable simulation state (called at init and on reset)."""
        self.corridor_id: Optional[str] = None
        self.state: str = "IDLE"          # top-level FSM state

        # Route data
        self.route_id: Optional[str] = None
        self.route_geometry: List[list] = []   # [[lon, lat], ...]
        self.distance_km: float = 0.0
        self.baseline_duration_min: float = 0.0
        self.optimized_duration_min: float = 0.0
        self.source: dict = {}
        self.destination_info: dict = {}

        # Ambulance simulation
        self._route_index: int = 0
        self._paused: bool = False
        self._sim_thread: Optional[threading.Thread] = None
        self._sim_running: bool = False
        self.ambulance_lat: float = 0.0
        self.ambulance_lon: float = 0.0
        self.current_speed_kmh: int = 0
        self.route_progress_pct: float = 0.0
        self.distance_remaining_km: float = 0.0
        self.eta_minutes: float = 0.0
        self.started_at: Optional[str] = None

        # Infrastructure state
        self.junctions: List[dict] = []
        self.vms_boards: List[dict] = []

        # Current point info (for UI)
        self.current_junction_name: Optional[str] = None
        self.next_junction_name: Optional[str] = None
        self.next_junction_distance_km: Optional[float] = None
        self.current_vms_message: str = DEFAULT_VMS_MESSAGE
        self.signal_phase: str = "normal"   # "normal" | "emergency_green"

        # Stats
        self.junctions_prioritised: int = 0
        self.vms_activated: int = 0
        self.anpr_detection_count: int = 0

        # ANPR
        self._anpr_started: bool = False
        self._anpr_start_time: Optional[float] = None
        self.anpr_history: List[dict] = []  # [{timestamp, plate, confidence, ...}]
        self._anpr_emitted_indices: set = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_destinations(self) -> List[dict]:
        """Return the list of available destinations from routes.json."""
        return deepcopy(self._destinations)

    def calculate_route(self, destination_id: str, osrm_result: dict) -> dict:
        """
        Called after the Flask route layer has fetched OSRM data.
        Loads the route-specific infrastructure JSON and merges with OSRM geometry.
        Returns the full route payload for the frontend.
        """
        with self._lock:
            # Find destination meta
            dest_meta = next(
                (d for d in self._destinations if d["id"] == destination_id), None
            )
            if dest_meta is None:
                raise ValueError(f"Unknown destination_id: {destination_id!r}")

            route_id = dest_meta["route_id"]

            # Load infrastructure JSON
            infra_path = _EMERGENCY_DATA / f"{route_id}.json"
            try:
                infra = _load_json(infra_path)
            except FileNotFoundError:
                raise ValueError(f"Infrastructure file not found: {infra_path}")

            # Extract OSRM values
            geometry = osrm_result.get("route", [])            # [[lon,lat],...]
            distance_km = float(osrm_result.get("distance_km", 0.0))
            osrm_duration_min = float(osrm_result.get("duration_min", 0.0))
            baseline_min = infra.get("baseline_time_minutes") or round(osrm_duration_min, 1)
            optimized_min = infra.get("prototype_optimized_time_minutes") or round(baseline_min * 0.5, 1)

            # Stash for when START is called
            self.state = "ROUTE_READY"
            self.route_id = route_id
            self.route_geometry = geometry
            self.distance_km = distance_km
            self.baseline_duration_min = baseline_min
            self.optimized_duration_min = optimized_min
            self.source = infra.get("source", {})
            self.destination_info = infra.get("destination", {})
            self.distance_remaining_km = distance_km
            self.eta_minutes = optimized_min

            # Initialise junction + VMS state from infra JSON
            # Pass previous point for auto-bearing of ambulance_approach
            infra_src = infra.get("source", {})
            prev_lat = float(infra_src.get("lat", 0.0))
            prev_lon = float(infra_src.get("lon", 0.0))
            self.junctions = []
            for j in infra.get("junctions", []):
                state = _build_junction_state(j, prev_lat, prev_lon)
                self.junctions.append(state)
                prev_lat = j["lat"]
                prev_lon = j["lon"]
            self.vms_boards = [_build_vms_state(v) for v in infra.get("vms", [])]

            # Set ambulance to source position
            src = infra.get("source", {})
            self.ambulance_lat = float(src.get("lat", 21.123028))
            self.ambulance_lon = float(src.get("lon", 79.051449))

            logger.info("Route calculated: %s  %.2f km  baseline=%s min  optimized=%s min",
                        route_id, distance_km, baseline_min, optimized_min)

            return {
                "route_id": route_id,
                "source": self.source,
                "destination": self.destination_info,
                "distance_km": distance_km,
                "baseline_duration_minutes": baseline_min,
                "optimized_duration_minutes": optimized_min,
                "geometry": geometry,
                "junctions": [{"id": j["id"], "name": j["name"],
                                "lat": j["lat"], "lon": j["lon"],
                                "sequence": j["sequence"]} for j in self.junctions],
                "vms": [{"id": v["id"], "name": v["name"],
                         "lat": v["lat"], "lon": v["lon"],
                         "sequence": v["sequence"]} for v in self.vms_boards],
            }

    def start(self, route_id: str) -> dict:
        """Start the ambulance simulation for the pre-calculated route."""
        with self._lock:
            if self.state not in ("ROUTE_READY", "IDLE"):
                raise RuntimeError(f"Cannot start in state {self.state!r}")
            if self.route_id != route_id:
                raise RuntimeError("route_id mismatch — call /api/emergency/route first")

            self.corridor_id = str(uuid.uuid4())[:8].upper()
            self.state = "EMERGENCY_STARTED"
            self._paused = False
            self._route_index = 0
            self.started_at = datetime.now(timezone.utc).isoformat()
            self.current_speed_kmh = random.randint(self._speed_min, self._speed_max)

            # Reset ANPR
            self._anpr_started = False
            self._anpr_start_time = None
            self.anpr_history = []
            self._anpr_emitted_indices = set()

            # Reset stats
            self.junctions_prioritised = 0
            self.vms_activated = 0
            self.anpr_detection_count = 0

            # Start background simulation thread
            self._sim_running = True
            self._sim_thread = threading.Thread(
                target=self._simulation_loop, daemon=True, name="corridor-sim"
            )
            self._sim_thread.start()

            logger.info("Emergency corridor STARTED: id=%s route=%s", self.corridor_id, route_id)
            return {"corridor_id": self.corridor_id, "status": "ACTIVE"}

    def pause(self) -> dict:
        with self._lock:
            self._paused = True
            self.current_speed_kmh = 0
            logger.info("Corridor PAUSED")
            return {"status": "PAUSED"}

    def resume(self) -> dict:
        with self._lock:
            self._paused = False
            self.current_speed_kmh = random.randint(self._speed_min, self._speed_max)
            logger.info("Corridor RESUMED")
            return {"status": "ACTIVE"}

    def reset(self) -> dict:
        """Stop everything and return to IDLE."""
        with self._lock:
            self._sim_running = False
            self._paused = False
        # Wait for sim thread outside lock to avoid deadlock
        if self._sim_thread and self._sim_thread.is_alive():
            self._sim_thread.join(timeout=3.0)
        with self._lock:
            self._reset_state()
            logger.info("Corridor RESET to IDLE")
            return {"status": "IDLE"}

    def get_status(self) -> dict:
        """Full status snapshot — called by the frontend polling loop."""
        with self._lock:
            # Find current and next junction names
            current_j = next((j for j in self.junctions if j["status"] == "active"), None)
            next_j = next((j for j in self.junctions if j["status"] == "pending"), None)

            # Active VMS message (first active-route VMS in emergency_warning)
            active_vms_msg = DEFAULT_VMS_MESSAGE
            active_vms_name = None
            for v in self.vms_boards:
                if v["status"] == "emergency_warning":
                    active_vms_msg = EMERGENCY_VMS_MESSAGE
                    active_vms_name = v["name"]
                    break

            # Signal colour for UI indicator
            sig_colour = "green" if self.signal_phase == "emergency_green" else "normal"

            return {
                "corridor_id": self.corridor_id,
                "state": self.state,
                "paused": self._paused,
                "route_id": self.route_id,
                "ambulance": {
                    "lat": self.ambulance_lat,
                    "lon": self.ambulance_lon,
                    "speed_kmh": self.current_speed_kmh,
                    "route_progress_pct": round(self.route_progress_pct, 2),
                    "distance_remaining_km": round(self.distance_remaining_km, 2),
                    "eta_minutes": round(self.eta_minutes, 1),
                },
                "current_junction": current_j["name"] if current_j else None,
                "next_junction": next_j["name"] if next_j else None,
                "next_junction_distance_km": round(
                    _haversine(self.ambulance_lat, self.ambulance_lon,
                               next_j["lat"], next_j["lon"]), 2
                ) if next_j and next_j["lat"] != 0.0 else None,
                "signal_phase": sig_colour,
                "current_junction_signals": current_j["emergency_signals"] if current_j else None,
                "current_vms_message": active_vms_msg,
                "active_vms_name": active_vms_name,
                "junctions": deepcopy(self.junctions),
                "vms_boards": deepcopy(self.vms_boards),
                "anpr": {
                    "started": self._anpr_started,
                    "history": list(reversed(self.anpr_history)),  # newest first
                },
                "stats": {
                    "junctions_prioritised": self.junctions_prioritised,
                    "vms_activated": self.vms_activated,
                    "anpr_detections": self.anpr_detection_count,
                    "baseline_duration_minutes": self.baseline_duration_min,
                    "optimized_duration_minutes": self.optimized_duration_min,
                    "time_saved_minutes": round(
                        self.baseline_duration_min - self.optimized_duration_min, 1
                    ),
                },
                "source": self.source,
                "destination": self.destination_info,
                "distance_km": self.distance_km,
                "started_at": self.started_at,
            }

    # ------------------------------------------------------------------
    # Background simulation loop
    # ------------------------------------------------------------------
    def _simulation_loop(self):
        """
        Advances the ambulance along the route geometry, updates junction
        and VMS states, emits ANPR log entries, and manages the FSM.

        Runs as a daemon thread — safe to abandon on process exit.
        """
        TICK = 0.5  # seconds between position updates

        while self._sim_running:
            time.sleep(TICK)

            with self._lock:
                if self._paused or not self._sim_running:
                    continue

                coords = self.route_geometry
                if not coords:
                    # No geometry — nothing to simulate; jump to completed
                    self._finish_corridor()
                    break

                total_points = len(coords)

                # --- advance position ---
                # Convert speed (km/h) to approximate waypoint steps per tick.
                # Each waypoint pair is typically ~10-30 m apart in OSRM output.
                # We use a fixed step that gives a visually smooth demo.
                if total_points > 1:
                    # Estimate metres per waypoint
                    total_route_m = self.distance_km * 1000.0
                    metres_per_wp = total_route_m / max(total_points - 1, 1)
                    speed_mps = self.current_speed_kmh * 1000.0 / 3600.0
                    steps = max(1, round((speed_mps * TICK) / max(metres_per_wp, 1.0)))
                else:
                    steps = 1

                self._route_index = min(self._route_index + steps, total_points - 1)
                point = coords[self._route_index]
                self.ambulance_lon = point[0]
                self.ambulance_lat = point[1]

                # Progress
                self.route_progress_pct = (self._route_index / max(total_points - 1, 1)) * 100.0
                self.distance_remaining_km = self.distance_km * (1.0 - self.route_progress_pct / 100.0)

                # ETA: simple distance / average speed estimate
                avg_speed_kmh = max(self.current_speed_kmh, 20)
                self.eta_minutes = (self.distance_remaining_km / avg_speed_kmh) * 60.0

                # Vary speed slightly for realism
                if random.random() < 0.15:
                    self.current_speed_kmh = random.randint(self._speed_min, self._speed_max)

                # --- junction logic ---
                self._update_junctions()

                # --- VMS logic ---
                self._update_vms()

                # --- ANPR logic ---
                self._update_anpr()

                # --- check arrival ---
                if self._route_index >= total_points - 1:
                    self._finish_corridor()
                    break

    # ------------------------------------------------------------------
    # Junction FSM
    # ------------------------------------------------------------------
    def _update_junctions(self):
        """Evaluate distance to each pending/active junction and update state."""
        for j in self.junctions:
            if j["status"] == "passed":
                continue

            # Skip junctions whose coordinates haven't been filled in yet
            if j["lat"] == 0.0 and j["lon"] == 0.0:
                # Simulate based on route progress fraction instead
                self._simulate_junction_by_progress(j)
                continue

            dist = _haversine(self.ambulance_lat, self.ambulance_lon, j["lat"], j["lon"])

            if j["status"] == "pending" and dist <= self._junction_trigger_km:
                j["status"] = "active"
                self.signal_phase = "emergency_green"
                self.junctions_prioritised += 1
                logger.debug("Junction ACTIVE: %s (%.3f km)", j["name"], dist)

            elif j["status"] == "active" and dist <= self._junction_passed_km:
                j["status"] = "passed"
                j["phase"] = "passed"
                self.signal_phase = "normal"
                # Trigger ANPR after first junction passed
                if not self._anpr_started and j["sequence"] == self._anpr_trigger_seq:
                    self._anpr_started = True
                    self._anpr_start_time = time.time()
                    logger.info("ANPR demo triggered after junction: %s", j["name"])
                logger.debug("Junction PASSED: %s", j["name"])

    def _simulate_junction_by_progress(self, j: dict):
        """
        Fallback when coordinates are placeholder (0.0, 0.0).
        Activates a junction when route progress matches expected sequence fraction.
        """
        total = len(self.junctions)
        trigger_pct = (j["sequence"] - 0.7) / total * 100.0
        passed_pct = (j["sequence"] - 0.1) / total * 100.0

        if j["status"] == "pending" and self.route_progress_pct >= trigger_pct:
            j["status"] = "active"
            self.signal_phase = "emergency_green"
            self.junctions_prioritised += 1
            logger.debug("Junction ACTIVE (progress): %s", j["name"])

        elif j["status"] == "active" and self.route_progress_pct >= passed_pct:
            j["status"] = "passed"
            j["phase"] = "passed"
            self.signal_phase = "normal"
            if not self._anpr_started and j["sequence"] == self._anpr_trigger_seq:
                self._anpr_started = True
                self._anpr_start_time = time.time()
                logger.info("ANPR demo triggered (progress): %s", j["name"])
            logger.debug("Junction PASSED (progress): %s", j["name"])

    # ------------------------------------------------------------------
    # VMS FSM
    # ------------------------------------------------------------------
    def _update_vms(self):
        """Evaluate distance to each VMS on the active route and update message."""
        for v in self.vms_boards:
            if v["status"] == "passed":
                continue

            if v["lat"] == 0.0 and v["lon"] == 0.0:
                self._simulate_vms_by_progress(v)
                continue

            dist = _haversine(self.ambulance_lat, self.ambulance_lon, v["lat"], v["lon"])

            if v["status"] == "normal" and dist <= self._vms_trigger_km:
                v["status"] = "emergency_warning"
                v["message"] = EMERGENCY_VMS_MESSAGE
                self.vms_activated += 1
                logger.debug("VMS EMERGENCY: %s (%.3f km)", v["name"], dist)

            elif v["status"] == "emergency_warning":
                # Check if ambulance has passed (it was moving toward the VMS;
                # once it moves further away again, consider it passed).
                # Simple heuristic: passed when progress moves beyond VMS sequence fraction
                total = len(self.vms_boards)
                passed_pct = (v["sequence"] / (total + 1)) * 100.0
                if self.route_progress_pct >= passed_pct + 5.0:
                    v["status"] = "passed"
                    v["message"] = DEFAULT_VMS_MESSAGE
                    logger.debug("VMS PASSED: %s", v["name"])

    def _simulate_vms_by_progress(self, v: dict):
        """Fallback VMS logic when coordinates are placeholder (0.0, 0.0)."""
        total = len(self.vms_boards)
        trigger_pct = ((v["sequence"] - 1) / max(total, 1)) * 100.0
        passed_pct = (v["sequence"] / max(total, 1)) * 100.0

        if v["status"] == "normal" and self.route_progress_pct >= trigger_pct:
            v["status"] = "emergency_warning"
            v["message"] = EMERGENCY_VMS_MESSAGE
            self.vms_activated += 1
            logger.debug("VMS EMERGENCY (progress): %s", v["name"])

        elif v["status"] == "emergency_warning" and self.route_progress_pct >= passed_pct:
            v["status"] = "passed"
            v["message"] = DEFAULT_VMS_MESSAGE
            logger.debug("VMS PASSED (progress): %s", v["name"])

    # ------------------------------------------------------------------
    # ANPR log emitter
    # ------------------------------------------------------------------
    def _update_anpr(self):
        """
        Once ANPR demo has been triggered, emit detection log entries in sync
        with video playback time (timestamp_sec from the JSON).
        """
        if not self._anpr_started or self._anpr_start_time is None:
            return

        elapsed = time.time() - self._anpr_start_time

        for idx, det in enumerate(self._anpr_detections):
            if idx in self._anpr_emitted_indices:
                continue
            if elapsed >= det["timestamp_sec"]:
                self._anpr_emitted_indices.add(idx)
                self.anpr_detection_count += 1
                self.anpr_history.append({
                    "log_time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                    "plate": det["plate"],
                    "confidence": det["confidence"],
                    "is_primary": det.get("is_primary", False),
                    "car_id": det["car_id"],
                    "source": det.get("source", "Ambulance CCTV"),
                    "frame": det["frame_number"],
                    "timestamp_sec": det["timestamp_sec"],
                })
                logger.debug("ANPR emit: %s (%.3f conf) at t=%.2fs",
                             det["plate"], det["confidence"], elapsed)

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------
    def _finish_corridor(self):
        """Called when ambulance reaches the destination."""
        self._sim_running = False
        self.state = "CORRIDOR_COMPLETED"
        self.route_progress_pct = 100.0
        self.distance_remaining_km = 0.0
        self.eta_minutes = 0.0
        self.current_speed_kmh = 0
        self.signal_phase = "normal"
        # Restore all VMS to default
        for v in self.vms_boards:
            v["message"] = DEFAULT_VMS_MESSAGE
        logger.info(
            "Corridor COMPLETED: junctions=%d vms=%d anpr=%d",
            self.junctions_prioritised, self.vms_activated, self.anpr_detection_count,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
corridor_service = EmergencyCorridorService()
