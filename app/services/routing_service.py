"""
Routing Service - calculates routes using OSRM or demo fallback.
"""

import logging
import math
from typing import List, Tuple, Optional
import requests

from app.config import OSRM_URL

logger = logging.getLogger(__name__)

# =============================================================================
# Demo route: Nagpur city coordinates (Medical College to AIIMS Nagpur area)
# =============================================================================
DEMO_ROUTES = {
    "default": {
        "start": {"lat": 21.1458, "lon": 79.0882, "name": "Nagpur Medical College"},
        "end": {"lat": 21.1260, "lon": 79.0467, "name": "AIIMS Nagpur"},
        "waypoints": [
            [79.0882, 21.1458],
            [79.0850, 21.1445],
            [79.0810, 21.1430],
            [79.0770, 21.1410],
            [79.0730, 21.1390],
            [79.0690, 21.1370],
            [79.0650, 21.1350],
            [79.0610, 21.1330],
            [79.0570, 21.1310],
            [79.0530, 21.1295],
            [79.0500, 21.1280],
            [79.0467, 21.1260],
        ],
        "junctions": [
            {"name": "Sitabuldi Junction", "lat": 21.1440, "lon": 79.0835, "index": 2},
            {"name": "Variety Square", "lat": 21.1400, "lon": 79.0750, "index": 4},
            {"name": "Dharampeth", "lat": 21.1350, "lon": 79.0650, "index": 6},
            {"name": "Law College Square", "lat": 21.1310, "lon": 79.0570, "index": 8},
            {"name": "AIIMS Gate", "lat": 21.1270, "lon": 79.0490, "index": 10},
        ],
    }
}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two lat/lon points."""
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


def calculate_route(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
) -> dict:
    """Calculate route using OSRM, with demo fallback."""

    # Try OSRM first
    try:
        route_data = _osrm_route(start_lat, start_lon, end_lat, end_lon)
        if route_data:
            logger.info("Route calculated via OSRM")
            return route_data
    except Exception as e:
        logger.warning(f"OSRM routing failed: {e}")

    # Fallback to demo route
    logger.info("Using DEMO routing mode")
    return _demo_route(start_lat, start_lon, end_lat, end_lon)


def _osrm_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> Optional[dict]:
    """Attempt OSRM routing."""
    url = (
        f"{OSRM_URL}/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
        f"?overview=full&geometries=geojson&steps=true"
    )

    try:
        resp = requests.get(url, timeout=10.0)
        if resp.status_code != 200:
            return None

        data = resp.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            return None

        route = data["routes"][0]
        coords = route["geometry"]["coordinates"]  # [[lon, lat], ...]
        distance_km = route["distance"] / 1000.0
        duration_min = route["duration"] / 60.0

        # Extract junction-like waypoints from steps
        junctions = []
        steps = route.get("legs", [{}])[0].get("steps", [])
        for i, step in enumerate(steps):
            if step.get("maneuver", {}).get("type") in ("turn", "end of road", "fork"):
                loc = step["maneuver"]["location"]
                junctions.append({
                    "name": step.get("name", f"Junction {i+1}") or f"Junction {i+1}",
                    "lat": loc[1],
                    "lon": loc[0],
                    "index": i,
                })

        # Ensure at least some junctions
        if not junctions and len(coords) > 4:
            step_size = max(1, len(coords) // 5)
            for idx in range(step_size, len(coords), step_size):
                if idx < len(coords):
                    junctions.append({
                        "name": f"Waypoint {len(junctions)+1}",
                        "lat": coords[idx][1],
                        "lon": coords[idx][0],
                        "index": idx,
                    })

        return {
            "routing_mode": "OSRM",
            "route": coords,
            "distance_km": round(distance_km, 2),
            "duration_min": round(duration_min, 2),
            "junctions": junctions,
        }
    except Exception as e:
        logger.error(f"OSRM Routing failed: {e}")
        return None


def _demo_route(
    start_lat: float, start_lon: float, end_lat: float, end_lon: float
) -> dict:
    """Provide a demo route with predefined Nagpur coordinates."""
    demo = DEMO_ROUTES["default"]
    waypoints = demo["waypoints"]
    junctions = []
    for j in demo["junctions"]:
        junctions.append({
            "name": j["name"],
            "lat": j["lat"],
            "lon": j["lon"],
            "index": j["index"],
            "status": "NORMAL",
        })

    # Calculate rough distance
    total_dist = 0.0
    for i in range(len(waypoints) - 1):
        total_dist += _haversine(
            waypoints[i][1], waypoints[i][0],
            waypoints[i + 1][1], waypoints[i + 1][0],
        )

    return {
        "routing_mode": "DEMO",
        "route": waypoints,
        "distance_km": round(total_dist, 2),
        "duration_min": round(total_dist / 0.5, 2),  # ~30 km/h avg
        "junctions": junctions,
    }


def geocode_destination(destination: str) -> Tuple[float, float]:
    """Resolve a destination string to coordinates, accepting any place name or lat/lon input."""
    if not destination or not destination.strip():
        logger.warning("Empty destination provided; using AIIMS Nagpur default")
        return (21.1260, 79.0467)

    value = destination.strip()
    lowered = value.lower()

    # Accept direct lat/lon input like "21.1260, 79.0467"
    try:
        if "," in value:
            parts = [p.strip() for p in value.split(",")]
            if len(parts) == 2:
                lat = float(parts[0])
                lon = float(parts[1])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return (lat, lon)
    except ValueError:
        pass

    known = {
        "aiims nagpur": (21.1260, 79.0467),
        "aiims": (21.1260, 79.0467),
        "nagpur medical college": (21.1458, 79.0882),
        "mayo hospital": (21.1497, 79.0856),
        "government medical college nagpur": (21.1458, 79.0882),
        "orange city hospital": (21.1350, 79.0640),
        "wockhardt hospital": (21.1330, 79.0720),
    }

    for k, v in known.items():
        if k in lowered or lowered in k:
            return v

    # Try remote geocoding through OpenStreetMap Nominatim for arbitrary user input.
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": value, "format": "jsonv2", "limit": 1},
            timeout=8.0,
            headers={"User-Agent": "SmartAmbulanceEmergencyApp/1.0"},
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0].get("lat"))
                lon = float(data[0].get("lon"))
                return (lat, lon)
    except Exception as exc:
        logger.warning(f"Nominatim geocoding failed for '{value}': {exc}")

    # Default: AIIMS Nagpur
    logger.warning(f"Unknown destination '{destination}', using AIIMS Nagpur default")
    return (21.1260, 79.0467)


# Default start location (Nagpur Medical College area)
DEFAULT_START = (21.1458, 79.0882)
