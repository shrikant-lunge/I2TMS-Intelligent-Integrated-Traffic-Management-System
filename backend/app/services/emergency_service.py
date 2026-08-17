"""
Emergency Service - manages emergency state, events, and lifecycle.
"""

import datetime
import logging
import threading
from typing import Optional

from sqlalchemy.orm import Session
from app.models.database import EmergencyEventDB, ViolationDB, SessionLocal

logger = logging.getLogger(__name__)


class EmergencyService:
    """Singleton service managing the current emergency state."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active_event: Optional[dict] = None
        self._event_counter = 0
        self._route: list = []
        self._junctions: list = []
        self._routing_mode: str = "DEMO"

    @property
    def is_active(self) -> bool:
        return self._active_event is not None and self._active_event.get("status") == "ACTIVE"

    @property
    def active_event(self) -> Optional[dict]:
        return self._active_event

    @property
    def active_event_id(self) -> Optional[str]:
        if self._active_event:
            return self._active_event.get("event_id")
        return None

    @property
    def route(self) -> list:
        return self._route

    @property
    def junctions(self) -> list:
        return self._junctions

    @property
    def routing_mode(self) -> str:
        return self._routing_mode

    def _generate_event_id(self) -> str:
        self._event_counter += 1
        year = datetime.datetime.now().year
        return f"AMB-{year}-{self._event_counter:04d}"

    def start_emergency(
        self,
        destination: str,
        start_lat: float,
        start_lon: float,
        dest_lat: float,
        dest_lon: float,
        route: list,
        junctions: list,
        routing_mode: str,
        ambulance_id: str = "AMB-DEFAULT-01",
    ) -> dict:
        """Activate a new emergency event."""
        with self._lock:
            # End any existing active emergency
            if self.is_active:
                self._end_current_event()

            event_id = self._generate_event_id()
            now = datetime.datetime.utcnow()

            self._active_event = {
                "event_id": event_id,
                "ambulance_id": ambulance_id,
                "destination": destination,
                "start_lat": start_lat,
                "start_lon": start_lon,
                "dest_lat": dest_lat,
                "dest_lon": dest_lon,
                "status": "ACTIVE",
                "routing_mode": routing_mode,
                "start_time": now.isoformat(),
            }
            self._route = route
            self._junctions = junctions
            self._routing_mode = routing_mode

            # Persist to database
            try:
                db = SessionLocal()
                db_event = EmergencyEventDB(
                    event_id=event_id,
                    ambulance_id=ambulance_id,
                    destination=destination,
                    start_lat=start_lat,
                    start_lon=start_lon,
                    dest_lat=dest_lat,
                    dest_lon=dest_lon,
                    status="ACTIVE",
                    routing_mode=routing_mode,
                    start_time=now,
                )
                db.add(db_event)
                db.commit()
                db.close()
            except Exception as e:
                logger.error(f"Failed to persist emergency event: {e}")

            logger.info(f"Emergency STARTED: {event_id} -> {destination}")
            return self._active_event.copy()

    def stop_emergency(self) -> Optional[dict]:
        """End the current active emergency."""
        with self._lock:
            if not self.is_active:
                return None
            return self._end_current_event()

    def _end_current_event(self) -> dict:
        """Internal: mark current event as completed."""
        event_id = self._active_event["event_id"]
        now = datetime.datetime.utcnow()
        self._active_event["status"] = "COMPLETED"
        self._active_event["end_time"] = now.isoformat()

        # Count violations for this event
        total_violations = 0
        try:
            db = SessionLocal()
            total_violations = (
                db.query(ViolationDB)
                .filter(ViolationDB.emergency_event_id == event_id)
                .count()
            )
            # Update DB record
            db_event = (
                db.query(EmergencyEventDB)
                .filter(EmergencyEventDB.event_id == event_id)
                .first()
            )
            if db_event:
                db_event.status = "COMPLETED"
                db_event.end_time = now
                db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Failed to update emergency event in DB: {e}")

        result = {
            "event_id": event_id,
            "status": "COMPLETED",
            "end_time": now.isoformat(),
            "total_violations": total_violations,
        }

        self._active_event = None
        self._route = []
        self._junctions = []

        logger.info(f"Emergency STOPPED: {event_id}, violations: {total_violations}")
        return result

    def get_status(self) -> dict:
        """Get current emergency status."""
        if self._active_event:
            return self._active_event.copy()
        return {"status": "INACTIVE"}


# Singleton instance
emergency_service = EmergencyService()
