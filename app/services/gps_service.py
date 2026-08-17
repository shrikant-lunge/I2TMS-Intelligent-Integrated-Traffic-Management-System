"""
GPS Service - GPS abstraction with simulation support.
Provides current position and geofencing for junctions.
"""

import math
import time
import logging
import threading
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class GPSService:
    """Simulates ambulance GPS movement along a route."""

    def __init__(self):
        self._lock = threading.Lock()
        self._route: List[List[float]] = []  # [[lon, lat], ...]
        self._junctions: List[dict] = []
        self._current_index: int = 0
        self._current_lat: float = 0.0
        self._current_lon: float = 0.0
        self._active: bool = False
        self._last_update: float = 0.0
        self._speed: float = 0.3  # waypoints per second
        self._next_junction_idx: int = 0
        self._geofence_radius_km: float = 0.3  # 300m geofence radius

    def start_simulation(
        self,
        route: List[List[float]],
        junctions: List[dict],
        start_lat: float,
        start_lon: float,
        simulate: bool = True,
    ):
        """Begin movement tracking. Default route simulation is enabled, but live user movement can disable it."""
        with self._lock:
            self._route = route
            self._junctions = junctions
            self._current_lat = start_lat
            self._current_lon = start_lon
            self._current_index = 0
            self._active = simulate
            self._last_update = time.time()
            self._next_junction_idx = 0
            # Set all junctions to NORMAL initially
            for j in self._junctions:
                j["status"] = "NORMAL"
            # First junction gets EMERGENCY_PRIORITY
            if self._junctions:
                self._junctions[0]["status"] = "EMERGENCY_PRIORITY"
            logger.info("GPS simulation started" if simulate else "GPS tracking set to live location mode")

    def set_current_position(self, lat: float, lon: float):
        """Update the ambulance position from the user laptop / live device location."""
        with self._lock:
            self._current_lat = lat
            self._current_lon = lon
            self._active = False
            self._last_update = time.time()
            logger.info(f"Live GPS position updated: ({lat}, {lon})")

    def stop_simulation(self):
        """Stop simulated movement."""
        with self._lock:
            self._active = False
            # Reset all junction statuses
            for j in self._junctions:
                j["status"] = "NORMAL"
            logger.info("GPS simulation stopped")

    def get_current_position(self) -> dict:
        """Get current GPS position."""
        with self._lock:
            if self._active:
                self._update_position()
            return {
                "lat": self._current_lat,
                "lon": self._current_lon,
                "active": self._active,
                "route_progress": self._current_index / max(len(self._route), 1),
            }

    def get_junctions(self) -> List[dict]:
        """Get junction statuses."""
        with self._lock:
            return [j.copy() for j in self._junctions]

    def get_next_junction(self) -> Optional[dict]:
        """Get the next upcoming junction."""
        with self._lock:
            if self._next_junction_idx < len(self._junctions):
                j = self._junctions[self._next_junction_idx].copy()
                j["distance_km"] = self._haversine(
                    self._current_lat, self._current_lon,
                    j["lat"], j["lon"]
                )
                return j
            return None

    def _update_position(self):
        """Advance position along route based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        if elapsed < 0.5:  # Update every 0.5s minimum
            return

        self._last_update = now
        steps = max(1, int(elapsed * self._speed))

        if self._route and self._current_index < len(self._route) - 1:
            self._current_index = min(
                self._current_index + steps,
                len(self._route) - 1,
            )
            point = self._route[self._current_index]
            self._current_lon = point[0]
            self._current_lat = point[1]

            # Update geofencing
            self._update_geofencing()

    def _update_geofencing(self):
        """Check if ambulance has passed a junction and update priorities."""
        if self._next_junction_idx >= len(self._junctions):
            return

        current_junction = self._junctions[self._next_junction_idx]
        dist = self._haversine(
            self._current_lat, self._current_lon,
            current_junction["lat"], current_junction["lon"],
        )

        # If we've passed the junction (within a small radius or gone past it)
        if dist < 0.05:  # ~50m, considered as "passed"
            current_junction["status"] = "NORMAL"
            self._next_junction_idx += 1
            logger.info(
                f"Passed junction: {current_junction['name']} -> NORMAL"
            )

            # Activate next junction
            if self._next_junction_idx < len(self._junctions):
                self._junctions[self._next_junction_idx]["status"] = "EMERGENCY_PRIORITY"
                logger.info(
                    f"Next junction: {self._junctions[self._next_junction_idx]['name']} -> EMERGENCY_PRIORITY"
                )

        # If approaching (within geofence radius), ensure it's marked
        elif dist < self._geofence_radius_km:
            if current_junction["status"] != "EMERGENCY_PRIORITY":
                current_junction["status"] = "EMERGENCY_PRIORITY"

    @staticmethod
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


# Singleton
gps_service = GPSService()
