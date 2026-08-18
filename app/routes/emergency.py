"""
Emergency Green Corridor — Flask Blueprint
==========================================
URL prefix: /api/emergency  (all endpoints)
Page routes: /emergency/driver  and  /admin/emergency-corridor

Endpoints
---------
GET  /emergency/driver                      → driver navigation screen (standalone)
GET  /admin/emergency-corridor              → admin monitoring screen  (extends base.html)
GET  /emergency-corridor                    → NMC admin list of all corridors
GET  /emergency-corridor/<corridor_id>      → detailed corridor view

POST /api/emergency/route                   → calculate OSRM route + load infrastructure
POST /api/emergency/start                   → start ambulance simulation
GET  /api/emergency/status/<corridor_id>    → live status poll (frontend calls every ~1s)
POST /api/emergency/pause                   → pause simulation
POST /api/emergency/resume                  → resume simulation
POST /api/emergency/reset                   → stop everything, return to IDLE
GET  /api/emergency/destinations            → list of selectable destinations
GET  /api/emergency/anpr-detections         → full ANPR detections JSON for frontend pre-load

GET  /api/emergency-corridors               → paginated corridor list (admin page)
GET  /api/emergency-corridor/<id>/live      → live status for detail page
GET  /emergency-corridor/<id>/export/anpr   → XLSX export of ANPR log
GET  /emergency-corridor/<id>/export/report → XLSX export of corridor report
"""

from __future__ import annotations

import io
import logging
import time

from flask import Blueprint, jsonify, render_template, request, send_file, redirect, url_for, session

from app.routes.dashboard import login_required
from app.services.emergency_corridor_service import corridor_service
from app.services.routing_service import calculate_route

logger = logging.getLogger(__name__)

emergency_bp = Blueprint("emergency_corridor", __name__)


def driver_login_required(f):
    """Decorator: ensures a driver session exists; else redirects to driver login."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("driver_id"):
            return redirect(url_for("auth.driver_login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@emergency_bp.route("/emergency/driver")
@driver_login_required
def driver_screen():
    """Ambulance driver navigation screen — standalone (no sidebar)."""
    return render_template(
        "emergency_driver.html",
        driver_username=session.get("driver_username", "Driver"),
        driver_mobile=session.get("driver_mobile", ""),
    )


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


# ---------------------------------------------------------------------------
# Page — Emergency Corridor admin list
# ---------------------------------------------------------------------------

@emergency_bp.route("/emergency-corridor")
@login_required
def corridor_list_page():
    """NMC admin list page: all emergency corridors."""
    return render_template(
        "emergency_corridor_list.html",
        active_page="emergency_corridor",
    )


@emergency_bp.route("/emergency-corridor/<corridor_id>")
@login_required
def corridor_detail_page(corridor_id: str):
    """Detail page for a single corridor."""
    from app.models.emergency_corridor_record import EmergencyCorridorRecord
    from app.models.emergency_corridor_event import EmergencyCorridorEvent
    from app.models.anpr_detection import ANPRDetection
    from app.models.emergency_metrics import EmergencyMetrics

    corridor = EmergencyCorridorRecord.query.filter_by(corridor_id=corridor_id).first_or_404()

    events = (
        EmergencyCorridorEvent.query
        .filter_by(corridor_id=corridor_id)
        .order_by(EmergencyCorridorEvent.created_at.asc())
        .all()
    )
    anpr_detections = (
        ANPRDetection.query
        .filter_by(corridor_id=corridor_id)
        .order_by(ANPRDetection.detected_at.asc())
        .all()
    )
    metrics = EmergencyMetrics.query.filter_by(corridor_id=corridor_id).first()

    return render_template(
        "emergency_corridor_detail.html",
        corridor_id=corridor_id,
        corridor=corridor,
        events=events,
        anpr_detections=anpr_detections,
        metrics=metrics,
        active_page="emergency_corridor",
    )


# ---------------------------------------------------------------------------
# API — paginated corridor list for the admin list page
# ---------------------------------------------------------------------------

@emergency_bp.route("/api/emergency-corridors")
@login_required
def api_corridor_list():
    from app.models.emergency_corridor_record import EmergencyCorridorRecord

    status_filter = request.args.get("status", "all")
    sort_by       = request.args.get("sort", "newest")
    page          = request.args.get("page", 1, type=int)
    per_page      = request.args.get("per_page", 10, type=int)

    query = EmergencyCorridorRecord.query

    if status_filter != "all":
        query = query.filter_by(status=status_filter.upper())

    if sort_by == "oldest":
        query = query.order_by(EmergencyCorridorRecord.created_at.asc())
    elif sort_by == "destination":
        query = query.order_by(EmergencyCorridorRecord.destination_name.asc())
    elif sort_by == "status":
        query = query.order_by(EmergencyCorridorRecord.status.asc(),
                               EmergencyCorridorRecord.created_at.desc())
    elif sort_by == "duration":
        query = query.order_by(EmergencyCorridorRecord.time_saved_minutes.desc().nullslast())
    else:  # newest
        query = query.order_by(EmergencyCorridorRecord.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    rows = []
    for c in pagination.items:
        ts = c.started_at or c.created_at
        rows.append({
            "corridor_id":    c.corridor_id,
            "source":         c.source_name,
            "destination":    c.destination_name,
            "status":         c.status,
            "started_at":     ts.strftime("%d %b %Y %I:%M %p") if ts else "—",
            "distance_km":    round(c.distance_km, 1) if c.distance_km else None,
            "baseline_eta":   round(c.baseline_eta_minutes) if c.baseline_eta_minutes else None,
            "optimized_eta":  round(c.optimized_eta_minutes) if c.optimized_eta_minutes else None,
            "time_saved":     round(c.time_saved_minutes, 1) if c.time_saved_minutes else None,
            "detail_url":     f"/emergency-corridor/{c.corridor_id}",
        })

    return jsonify({
        "rows": rows,
        "pagination": {
            "current_page": pagination.page,
            "per_page":     pagination.per_page,
            "total_rows":   pagination.total,
            "total_pages":  pagination.pages,
        },
    })


# ---------------------------------------------------------------------------
# API — live counts for the detail page (active corridors)
# ---------------------------------------------------------------------------

@emergency_bp.route("/api/emergency-corridor/<corridor_id>/live")
@login_required
def api_corridor_live(corridor_id: str):
    from app.models.anpr_detection import ANPRDetection
    from app.models.emergency_corridor_record import EmergencyCorridorRecord

    rec = EmergencyCorridorRecord.query.filter_by(corridor_id=corridor_id).first()
    if rec is None:
        return jsonify({"error": "not found"}), 404

    anpr_count = ANPRDetection.query.filter_by(corridor_id=corridor_id).count()
    return jsonify({
        "corridor_id": corridor_id,
        "status":      rec.status,
        "anpr_count":  anpr_count,
    })


# ---------------------------------------------------------------------------
# XLSX exports
# ---------------------------------------------------------------------------

@emergency_bp.route("/emergency-corridor/<corridor_id>/export/anpr")
@login_required
def export_anpr_xlsx(corridor_id: str):
    """Download ANPR detection log as XLSX."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return "openpyxl is required for XLSX export. Run: pip install openpyxl", 500

    from app.models.anpr_detection import ANPRDetection
    from app.models.emergency_corridor_record import EmergencyCorridorRecord

    corridor = EmergencyCorridorRecord.query.filter_by(corridor_id=corridor_id).first_or_404()
    detections = (
        ANPRDetection.query
        .filter_by(corridor_id=corridor_id)
        .order_by(ANPRDetection.detected_at.asc())
        .all()
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ANPR Log"

    # Header styling
    header_fill = PatternFill("solid", fgColor="1A2942")
    header_font = Font(color="FFFFFF", bold=True, size=10)

    headers = [
        "Corridor ID", "Plate Number", "Confidence (%)", "Is Primary",
        "Car ID", "Detected At", "Video Timestamp (s)",
        "Latitude", "Longitude", "Checkpoint", "Source", "Image Path",
    ]
    ws.append(headers)
    for col_idx, _ in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for det in detections:
        ws.append([
            corridor_id,
            det.plate_number,
            round(det.confidence * 100, 1) if det.confidence else "",
            "Yes" if det.is_primary else "No",
            det.car_id or "",
            det.detected_at.strftime("%Y-%m-%d %H:%M:%S") if det.detected_at else "",
            det.video_timestamp_sec or "",
            det.latitude or "",
            det.longitude or "",
            det.checkpoint_name or "",
            det.source or "",
            det.image_path or "",
        ])

    # Auto-fit columns
    for col in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col), default=8)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"ANPR_Log_{corridor_id}.xlsx",
    )


@emergency_bp.route("/emergency-corridor/<corridor_id>/export/report")
@login_required
def export_corridor_report_xlsx(corridor_id: str):
    """Download full corridor report as XLSX."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        return "openpyxl is required for XLSX export. Run: pip install openpyxl", 500

    from app.models.emergency_corridor_record import EmergencyCorridorRecord
    from app.models.emergency_corridor_event import EmergencyCorridorEvent
    from app.models.anpr_detection import ANPRDetection
    from app.models.emergency_metrics import EmergencyMetrics

    corridor   = EmergencyCorridorRecord.query.filter_by(corridor_id=corridor_id).first_or_404()
    metrics    = EmergencyMetrics.query.filter_by(corridor_id=corridor_id).first()
    events     = (EmergencyCorridorEvent.query.filter_by(corridor_id=corridor_id)
                  .order_by(EmergencyCorridorEvent.created_at.asc()).all())
    detections = (ANPRDetection.query.filter_by(corridor_id=corridor_id)
                  .order_by(ANPRDetection.detected_at.asc()).all())

    wb = openpyxl.Workbook()
    header_fill = PatternFill("solid", fgColor="1A2942")
    header_font = Font(color="FFFFFF", bold=True, size=10)

    def _make_header(ws, cols):
        ws.append(cols)
        for i, _ in enumerate(cols, 1):
            c = ws.cell(row=1, column=i)
            c.fill = header_fill
            c.font = header_font
            c.alignment = Alignment(horizontal="center")

    def _autofit(ws):
        for col in ws.columns:
            ml = max((len(str(c.value or "")) for c in col), default=8)
            ws.column_dimensions[col[0].column_letter].width = min(ml + 4, 40)

    # Sheet 1 — Summary
    ws1 = wb.active
    ws1.title = "Summary"
    summary_rows = [
        ("Corridor ID",        corridor.corridor_id),
        ("Source",             corridor.source_name),
        ("Destination",        corridor.destination_name),
        ("Status",             corridor.status),
        ("Distance (km)",      round(corridor.distance_km, 1) if corridor.distance_km else ""),
        ("Baseline ETA (min)", round(corridor.baseline_eta_minutes) if corridor.baseline_eta_minutes else ""),
        ("Optimized ETA (min)",round(corridor.optimized_eta_minutes) if corridor.optimized_eta_minutes else ""),
        ("Time Saved (min)",   round(corridor.time_saved_minutes, 1) if corridor.time_saved_minutes else ""),
        ("Started At",         corridor.started_at.strftime("%Y-%m-%d %H:%M:%S") if corridor.started_at else ""),
        ("Completed At",       corridor.completed_at.strftime("%Y-%m-%d %H:%M:%S") if corridor.completed_at else ""),
    ]
    if metrics:
        summary_rows += [
            ("Junctions Crossed",  metrics.junctions_crossed),
            ("Signals Prioritized",metrics.signals_prioritized),
            ("VMS Activated",      metrics.vms_activated),
            ("ANPR Detections",    metrics.anpr_detections),
        ]
    for label, val in summary_rows:
        ws1.append([label, val])
    ws1.column_dimensions["A"].width = 25
    ws1.column_dimensions["B"].width = 30

    # Sheet 2 — Events
    ws2 = wb.create_sheet("Events")
    _make_header(ws2, ["Timestamp", "Event Type", "Description", "Latitude", "Longitude", "VMS ID"])
    for ev in events:
        ws2.append([
            ev.created_at.strftime("%Y-%m-%d %H:%M:%S") if ev.created_at else "",
            ev.event_type,
            ev.description or "",
            ev.latitude or "",
            ev.longitude or "",
            ev.vms_id or "",
        ])
    _autofit(ws2)

    # Sheet 3 — ANPR
    ws3 = wb.create_sheet("ANPR Log")
    _make_header(ws3, ["Plate Number", "Confidence (%)", "Is Primary", "Car ID",
                       "Detected At", "Video Timestamp (s)", "Latitude", "Longitude",
                       "Checkpoint", "Source"])
    for det in detections:
        ws3.append([
            det.plate_number,
            round(det.confidence * 100, 1) if det.confidence else "",
            "Yes" if det.is_primary else "No",
            det.car_id or "",
            det.detected_at.strftime("%Y-%m-%d %H:%M:%S") if det.detected_at else "",
            det.video_timestamp_sec or "",
            det.latitude or "",
            det.longitude or "",
            det.checkpoint_name or "",
            det.source or "",
        ])
    _autofit(ws3)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Corridor_Report_{corridor_id}.xlsx",
    )
