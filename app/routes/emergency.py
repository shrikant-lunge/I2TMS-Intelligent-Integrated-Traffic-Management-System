"""
Emergency Green Corridor — Flask Blueprint
==========================================
URL prefix: /api/emergency  (all endpoints)
Page routes: /emergency/driver  and  /admin/emergency-corridor

Endpoints
---------
GET  /emergency/driver                      → driver navigation screen (standalone)
GET  /admin/emergency-corridor              → admin monitoring screen  (extends base.html)

POST /api/emergency/route                   → calculate OSRM route + load infrastructure
POST /api/emergency/start                   → start ambulance simulation
GET  /api/emergency/status/<corridor_id>    → live status poll (frontend calls every ~1s)
POST /api/emergency/pause                   → pause simulation
POST /api/emergency/resume                  → resume simulation
POST /api/emergency/reset                   → stop everything, return to IDLE
GET  /api/emergency/destinations            → list of selectable destinations
GET  /api/emergency/anpr-detections         → full ANPR detections JSON for frontend pre-load
"""

from __future__ import annotations

import logging
import time

from flask import Blueprint, jsonify, render_template, request

from app.routes.dashboard import login_required
from app.services.emergency_corridor_service import corridor_service
from app.services.routing_service import calculate_route

logger = logging.getLogger(__name__)

emergency_bp = Blueprint("emergency_corridor", __name__)


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@emergency_bp.route("/emergency/driver")
def driver_screen():
    """Ambulance driver navigation screen — standalone (no sidebar)."""
    return render_template("emergency_driver.html")


@emergency_bp.route("/admin/emergency-corridor")
@login_required
def admin_corridor_screen():
    """Admin / NMC control-room corridor monitoring screen."""
    return render_template(
        "emergency_admin.html",
        active_page="emergency_corridor",
    )


# ---------------------------------------------------------------------------
# API — destinations list
# ---------------------------------------------------------------------------

@emergency_bp.route("/api/emergency/destinations")
def api_destinations():
    """Return the three selectable destination hospitals."""
    try:
        dests = corridor_service.get_destinations()
        return jsonify({"status": "success", "destinations": dests})
    except Exception as exc:
        logger.exception("Failed to get destinations")
        return jsonify({"status": "error", "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# API — calculate route
# ---------------------------------------------------------------------------

@emergency_bp.route("/api/emergency/route", methods=["POST"])
def api_calculate_route():
    """
    POST /api/emergency/route
    Body: { "destination_id": "aiims" | "lata_mangeshkar" | "gmc" }

    1. Looks up destination coordinates from routes.json
    2. Calls OSRM with VNIT as source
    3. Loads route infrastructure JSON
    4. Returns full route payload for the frontend
    """
    body = request.get_json(force=True) or {}
    destination_id = body.get("destination_id", "").strip()

    if not destination_id:
        return jsonify({"status": "error", "message": "destination_id is required"}), 400

    # Find destination meta from corridor_service
    dests = corridor_service.get_destinations()
    dest_meta = next((d for d in dests if d["id"] == destination_id), None)
    if dest_meta is None:
        return jsonify({"status": "error", "message": f"Unknown destination_id: {destination_id!r}"}), 400

    # VNIT Nagpur — fixed source for this prototype
    VNIT_LAT = 21.123028
    VNIT_LON = 79.051449

    dest_lat = float(dest_meta["lat"])
    dest_lon = float(dest_meta["lon"])

    # Call OSRM (with demo fallback in routing_service)
    try:
        osrm_result = calculate_route(VNIT_LAT, VNIT_LON, dest_lat, dest_lon)
    except Exception as exc:
        logger.warning("OSRM call failed: %s — using demo geometry", exc)
        osrm_result = {
            "routing_mode": "DEMO",
            "route": [[VNIT_LON, VNIT_LAT], [dest_lon, dest_lat]],
            "distance_km": 15.0,
            "duration_min": 30.0,
            "junctions": [],
        }

    # Let the corridor service merge infrastructure + OSRM
    try:
        route_payload = corridor_service.calculate_route(destination_id, osrm_result)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        logger.exception("calculate_route failed")
        return jsonify({"status": "error", "message": str(exc)}), 500

    return jsonify({"status": "success", "data": route_payload})


# ---------------------------------------------------------------------------
# API — start corridor
# ---------------------------------------------------------------------------

@emergency_bp.route("/api/emergency/start", methods=["POST"])
def api_start():
    """
    POST /api/emergency/start
    Body: { "route_id": "vnit_to_aiims" }

    Starts the ambulance simulation.  /api/emergency/route must have been
    called first for this route_id.
    """
    body = request.get_json(force=True) or {}
    route_id = body.get("route_id", "").strip()

    if not route_id:
        return jsonify({"status": "error", "message": "route_id is required"}), 400

    try:
        result = corridor_service.start(route_id)
        return jsonify({"status": "success", "data": result})
    except RuntimeError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 409
    except Exception as exc:
        logger.exception("Failed to start corridor")
        return jsonify({"status": "error", "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# API — status poll
# ---------------------------------------------------------------------------

@emergency_bp.route("/api/emergency/status")
@emergency_bp.route("/api/emergency/status/<corridor_id>")
def api_status(corridor_id: str | None = None):
    """
    GET /api/emergency/status[/<corridor_id>]

    Returns live status of the active corridor.
    The corridor_id path param is accepted but ignored — there is at most
    one active corridor in this prototype.
    """
    try:
        status = corridor_service.get_status()
        return jsonify({"status": "success", "data": status})
    except Exception as exc:
        logger.exception("Failed to get status")
        return jsonify({"status": "error", "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# API — pause / resume
# ---------------------------------------------------------------------------

@emergency_bp.route("/api/emergency/pause", methods=["POST"])
def api_pause():
    try:
        result = corridor_service.pause()
        return jsonify({"status": "success", "data": result})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@emergency_bp.route("/api/emergency/resume", methods=["POST"])
def api_resume():
    try:
        result = corridor_service.resume()
        return jsonify({"status": "success", "data": result})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# API — reset
# ---------------------------------------------------------------------------

@emergency_bp.route("/api/emergency/reset", methods=["POST"])
def api_reset():
    """
    POST /api/emergency/reset

    Stops the active simulation and returns the service to IDLE.
    All junction/VMS/ANPR state is cleared.
    """
    try:
        result = corridor_service.reset()
        return jsonify({"status": "success", "data": result})
    except Exception as exc:
        logger.exception("Failed to reset corridor")
        return jsonify({"status": "error", "message": str(exc)}), 500


# ---------------------------------------------------------------------------
# API — ANPR detections pre-load
# ---------------------------------------------------------------------------

@emergency_bp.route("/api/emergency/anpr-detections")
def api_anpr_detections():
    """
    GET /api/emergency/anpr-detections

    Returns the full ANPR detections JSON so the frontend can pre-load
    the list and sync playback against video currentTime.
    """
    import json
    from pathlib import Path

    try:
        data_path = (
            Path(__file__).resolve().parent.parent.parent
            / "data" / "emergency" / "anpr_detections.json"
        )
        with open(data_path, encoding="utf-8") as fh:
            data = json.load(fh)
        return jsonify({"status": "success", "data": data})
    except Exception as exc:
        logger.exception("Failed to serve anpr_detections.json")
        return jsonify({"status": "error", "message": str(exc)}), 500
