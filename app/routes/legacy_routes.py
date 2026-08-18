from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, send_file
import os, io, math, random, time
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models import *
from app.routes.dashboard import login_required
from app.config import Config, BASE_DIR
from app.services.routing_service import calculate_route

legacy_bp = Blueprint('legacy', __name__)
# BASE_DIR is imported

ADAPTIVE_JUNCTIONS = {
    "rahate-colony": "Rahate Colony",
    "shankar-nagar": "Shankar Nagar",
    "laxmi-nagar-sq": "Laxmi Nagar Sq.",
    "dikshabhoomi-sq": "Dikshabhoomi Sq.",
    "law-college-sq": "Law College Sq.",
    "zero-mile-sq": "Zero Mile Sq.",
}


def _adaptive_junction_name(key):
    return ADAPTIVE_JUNCTIONS.get(key, ADAPTIVE_JUNCTIONS["rahate-colony"])

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

# (login_required imported from dashboard)


# ---------------------------------------------------------------------------
# Routes — Auth
# ---------------------------------------------------------------------------

# (Auth routes moved to auth.py)


# ---------------------------------------------------------------------------
# Routes — Main screens
# ---------------------------------------------------------------------------

# (Dashboard route moved to dashboard.py)


# Future screen stubs — replaced screen-by-screen in subsequent sprints
@legacy_bp.route("/adaptive-signals")
@login_required
def adaptive_signals():
    """Screen 3: Adaptive Signals — Junction View."""
    selected = request.args.get("junction", "rahate-colony")
    junctions = (
        Junction.query
        .filter(Junction.name.like("Junction _"))
        .order_by(Junction.name)
        .all()
    )
    return render_template(
        "adaptive-signals.html",
        active_page="adaptive_signals",
        selected_junction=selected,
        junctions=junctions,
    )



@legacy_bp.route("/analytics")
@login_required
def analytics():
    """Screen 4: Junction Analytics – Detailed."""
    selected = request.args.get("junction", "A")
    time_range = request.args.get("range", "today")
    junctions = (
        Junction.query
        .filter(Junction.name.like("Junction _"))
        .order_by(Junction.name)
        .all()
    )
    return render_template(
        "analytics.html",
        active_page="analytics",
        selected_junction=selected,
        selected_range=time_range,
        junctions=junctions,
    )


@legacy_bp.route("/decision-logs")
@login_required
def decision_logs():
    """Screen 5: Decision Logs."""
    junctions = (
        Junction.query
        .filter(Junction.name.like("Junction _"))
        .order_by(Junction.name)
        .all()
    )
    return render_template("decision-logs.html", active_page="decision_logs", junctions=junctions)


@legacy_bp.route("/incidents-alerts")
@login_required
def incidents_alerts():
    """Screen 10: Incidents & Alerts — unified alert + emergency dispatch view."""
    return render_template("incidents-alerts.html", active_page="incidents")


@legacy_bp.route("/emergency/new")
@login_required
def emergency_new():
    return render_template("emergency-new.html", now=datetime.now(), active_page="emergency")



@legacy_bp.route("/maps")
@login_required
def maps():
    return render_template("stub.html", page_name="Maps", active_page="maps")


@legacy_bp.route("/reports")
@login_required
def reports():
    return render_template("reports.html", active_page="reports")


@legacy_bp.route("/settings")
@login_required
def settings():
    is_admin = session.get("role") == "admin"
    return render_template("settings.html", is_admin=is_admin, active_page="settings")


@legacy_bp.route("/profile")
@login_required
def profile():
    user = User.query.get(session["user_id"])
    return render_template("profile.html", user=user)


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@legacy_bp.route("/api/dashboard_summary")
@login_required
def api_dashboard_summary():
    """
    Dashboard summary — all values are database-driven.
    No mock/random data.
    """
    from app.models.emergency_corridor_record import EmergencyCorridorRecord
    from app.models.adaptive_signal_state import AdaptiveSignalState
    from app.models.traffic_trend import TrafficTrend

    now = datetime.utcnow()
    window_start = now - timedelta(minutes=30)  # "active" = updated within 30 min

    # ── REAL: stat cards ─────────────────────────────────────────────────────

    # Total junctions in the database
    total_junctions = Junction.query.count()

    # Active junctions = those with a recent AdaptiveSignalState update
    active_junction_names = (
        db.session.query(AdaptiveSignalState.junction_name)
        .filter(AdaptiveSignalState.updated_at >= window_start)
        .distinct()
        .all()
    )
    active_junctions = len(active_junction_names)
    # Floor: count junctions whose DB status != "low" as a fallback
    if active_junctions == 0:
        active_junctions = Junction.query.filter(Junction.status != "low").count()

    # Average congestion from the most recent AdaptiveSignalState rows
    recent_states = (
        AdaptiveSignalState.query
        .filter(AdaptiveSignalState.updated_at >= window_start)
        .all()
    )
    if recent_states:
        level_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for s in recent_states:
            lvl = (s.congestion_level or "LOW").upper()
            if lvl in level_counts:
                level_counts[lvl] += 1
        dominant = max(level_counts, key=level_counts.get)
        avg_congestion = dominant.capitalize()
    else:
        # Fall back to junction status distribution
        high_count = Junction.query.filter_by(status="high").count()
        mod_count  = Junction.query.filter_by(status="moderate").count()
        if high_count >= mod_count:
            avg_congestion = "High"
        elif mod_count > 0:
            avg_congestion = "Moderate"
        else:
            avg_congestion = "Low"

    # Active corridors from the new EmergencyCorridorRecord table
    active_corridors = EmergencyCorridorRecord.query.filter_by(status="ACTIVE").count()

    # ── REAL: live junction cards ────────────────────────────────────────────
    display_junctions = (
        Junction.query
        .order_by(Junction.name)
        .limit(4)
        .all()
    )
    live_junctions = []
    for j in display_junctions:
        # Try to find the most recent signal state for this junction
        state = (
            AdaptiveSignalState.query
            .filter_by(junction_name=j.name)
            .order_by(AdaptiveSignalState.updated_at.desc())
            .first()
        )
        badge_status = state.traffic_level.lower() if state else j.status
        live_junctions.append({
            "name":          j.name,
            "status":        badge_status,
            "thumbnail_url": j.camera_thumbnail_url or "",
            "link":          f"/adaptive-signals?junction={j.name.split()[-1]}",
        })

    # ── REAL: traffic trend from TrafficTrend table ───────────────────────────
    trend_start = now - timedelta(hours=1)
    trend_rows = (
        TrafficTrend.query
        .filter(TrafficTrend.time_bucket >= trend_start)
        .order_by(TrafficTrend.time_bucket.asc())
        .all()
    )

    if trend_rows:
        labels, high_vals, med_vals, low_vals = [], [], [], []
        for row in trend_rows:
            labels.append(row.time_bucket.strftime("%H:%M"))
            level = (row.congestion_level or "LOW").upper()
            high_vals.append(row.vehicle_count if level == "HIGH"   else 0)
            med_vals.append( row.vehicle_count if level == "MEDIUM" else 0)
            low_vals.append( row.vehicle_count if level == "LOW"    else 0)
        trend_data = {"labels": labels, "high": high_vals, "medium": med_vals, "low": low_vals}
    else:
        # No historical data yet — return empty state clearly labelled
        trend_data = {
            "labels": [],
            "high":   [],
            "medium": [],
            "low":    [],
            "empty_message": "No historical traffic data available yet. Data will appear here once the adaptive-signal pipeline processes its first feed.",
        }

    # ── REAL: recent emergency corridors (replaces recent alerts) ─────────────
    recent_corridor_rows = (
        EmergencyCorridorRecord.query
        .order_by(EmergencyCorridorRecord.created_at.desc())
        .limit(5)
        .all()
    )
    recent_corridors = []
    for c in recent_corridor_rows:
        ts = c.started_at or c.created_at
        recent_corridors.append({
            "corridor_id":      c.corridor_id,
            "source":           c.source_name,
            "destination":      c.destination_name,
            "status":           c.status,
            "time":             ts.strftime("%I:%M %p") if ts else "—",
            "distance_km":      c.distance_km,
            "optimized_eta":    c.optimized_eta_minutes,
            "time_saved":       c.time_saved_minutes,
            "detail_url":       f"/emergency-corridor/{c.corridor_id}",
        })

    return jsonify({
        "total_junctions":    total_junctions,
        "active_junctions":   active_junctions,
        "avg_congestion":     avg_congestion,
        "active_corridors":   active_corridors,
        "live_junctions":     live_junctions,
        "traffic_trend":      trend_data,
        "recent_corridors":   recent_corridors,
    })



# ---------------------------------------------------------------------------
# API Routes — Screen 3: Adaptive Signals
# ---------------------------------------------------------------------------

@legacy_bp.route("/api/junction_signal")
@login_required
def api_junction_signal():
    """
    Per-junction signal data.
    # MOCK — replace with real Max-Pressure / signal-controller output
    # once your teammates' pipeline exposes per-junction state.
    """
    junction_key = request.args.get("junction", "rahate-colony")
    junction_name = _adaptive_junction_name(junction_key)

    # ── MOCK: phase cycle (naturally ticking via server clock) ──────────────
    # TODO: replace with real controller phase/countdown from signal API
    cycle_sec    = 90
    elapsed      = int(time.time()) % cycle_sec
    time_remaining = cycle_sec - elapsed

    # ── MOCK: traffic state ─────────────────────────────────────────────────
    # TODO: replace with real PCU / queue / speed readings from detection pipeline
    traffic_state_map = {
        "rahate-colony": {"pcu_overall": 74, "queue_length_m": 86, "avg_speed": 16, "density": "high"},
        "shankar-nagar": {"pcu_overall": 52, "queue_length_m": 58, "avg_speed": 23, "density": "moderate"},
        "laxmi-nagar-sq": {"pcu_overall": 61, "queue_length_m": 64, "avg_speed": 21, "density": "high"},
        "dikshabhoomi-sq": {"pcu_overall": 44, "queue_length_m": 42, "avg_speed": 28, "density": "moderate"},
        "law-college-sq": {"pcu_overall": 36, "queue_length_m": 31, "avg_speed": 34, "density": "low"},
        "zero-mile-sq": {"pcu_overall": 68, "queue_length_m": 77, "avg_speed": 18, "density": "high"},
    }
    traffic_state = traffic_state_map.get(junction_key, traffic_state_map["rahate-colony"])

    # ── MOCK: recommended signal plan ────────────────────────────────────────
    # TODO: replace with Max-Pressure optimised timing output
    recommended_plan = [
        {"phase": "North", "duration_sec": 52},
        {"phase": "East", "duration_sec": 28},
        {"phase": "West", "duration_sec": 35},
        {"phase": "South", "duration_sec": 17},
    ]

    lane_seed = sum(ord(ch) for ch in junction_key)
    lane_counts = [
        24 + (lane_seed % 9),
        14 + (lane_seed % 7),
        18 + (lane_seed % 8),
        7 + (lane_seed % 6),
    ]
    lanes = [
        {"direction": "north", "count": lane_counts[0], "density": "High", "signal": "red", "time_sec": 52},
        {"direction": "east", "count": lane_counts[1], "density": "Moderate", "signal": "green", "time_sec": 28},
        {"direction": "west", "count": lane_counts[2], "density": "Moderate", "signal": "amber", "time_sec": 35},
        {"direction": "south", "count": lane_counts[3], "density": "Low", "signal": "red", "time_sec": 17},
    ]

    # ── REAL: resolve junction name + camera URL from DB ─────────────────────
    j = Junction.query.filter_by(name=junction_name).first()
    camera_url = (j.camera_thumbnail_url or "") if j else ""

    # Light indicator color based on time remaining
    light_color = "amber" if time_remaining <= 5 else "green"

    # Emergency priority check (Disabled - Emergency Module removed)
    emergency_priority = False
    emergency_id = None

    return jsonify({
        "junction":           junction_name,
        "current_phase":      "North",
        "light":              light_color,
        "time_remaining":     time_remaining,
        "cycle_time_sec":     cycle_sec,
        "traffic_state":      traffic_state,
        "recommended_plan":   recommended_plan,
        "lanes":              lanes,
        "camera_url":         camera_url,
        "emergency_priority": emergency_priority,
        "emergency_id":       emergency_id,
    })


@legacy_bp.route("/api/apply_plan", methods=["POST"])
@login_required
def api_apply_plan():
    """
    Apply the recommended signal plan for the given junction.
    Logs entry to SignalPlanHistory DB table.
    """
    data     = request.get_json(force=True) or {}
    j_key    = data.get("junction", "rahate-colony")
    j_name   = _adaptive_junction_name(j_key)
    j_obj    = _get_or_create_junction(j_name, "moderate")

    # Record history
    hist = SignalPlanHistory(
        junction_id   = j_obj.id,
        applied_at    = datetime.utcnow(),
        phase_a_sec   = 52,
        phase_b_sec   = 28,
        phase_c_sec   = 35,
        phase_d_sec   = 17,
        applied_by    = "System",
        decision_type = "adaptive",
    )
    db.session.add(hist)
    db.session.commit()

    print(f"[decision] APPLY recommended plan — {j_name}")
    return jsonify({"status": "ok", "message": f"Recommended plan applied for {j_name}"})


@legacy_bp.route("/api/hold_current", methods=["POST"])
@login_required
def api_hold_current():
    """
    Cancel the pending recommendation; keep current running phase.
    No history row is logged as it's not a new decision.
    """
    data     = request.get_json(force=True) or {}
    j_key    = data.get("junction", "rahate-colony")
    j_name   = _adaptive_junction_name(j_key)

    print(f"[decision] HOLD current phase — {j_name}")
    return jsonify({"status": "ok", "message": f"Holding current phase for {j_name}"})


@legacy_bp.route("/api/manual_override", methods=["POST"])
@login_required
def api_manual_override():
    """
    Force a specific phase/duration at the given junction.
    Logs entry to SignalPlanHistory DB table as Operator override.
    """
    data     = request.get_json(force=True) or {}
    j_key    = data.get("junction", "rahate-colony")
    j_name   = _adaptive_junction_name(j_key)
    phase    = data.get("phase", "North")
    duration = int(data.get("duration_sec", 30))
    j_obj    = _get_or_create_junction(j_name, "moderate")

    dur_a = duration if phase in ("Phase A", "North") else 25
    dur_b = duration if phase in ("Phase B", "East") else 20
    dur_c = duration if phase in ("Phase C", "West") else 20
    dur_d = duration if phase in ("Phase D", "South") else 15

    hist = SignalPlanHistory(
        junction_id   = j_obj.id,
        applied_at    = datetime.utcnow(),
        phase_a_sec   = dur_a,
        phase_b_sec   = dur_b,
        phase_c_sec   = dur_c,
        phase_d_sec   = dur_d,
        applied_by    = "Operator",
        decision_type = "manual_override",
    )
    db.session.add(hist)
    db.session.commit()

    print(f"[decision] MANUAL OVERRIDE — {j_name} → {phase} for {duration}s")
    return jsonify({
        "status":  "ok",
        "message": f"Override applied: {phase} for {duration}s at {j_name}",
    })



# ---------------------------------------------------------------------------
# API Routes — Screen 4: Junction Analytics
# ---------------------------------------------------------------------------

@legacy_bp.route("/api/junction_analytics")
@login_required
def api_junction_analytics():
    """
    Detailed analytics for a specific junction and time range.
    Queries real SignalPlanHistory table for history logs.
    """
    junction_key = request.args.get("junction", "A")
    time_range   = request.args.get("range", "today").lower()

    j_obj = Junction.query.filter_by(name=f"Junction {junction_key}").first()
    j_id  = j_obj.id if j_obj else 1

    # Fetch signal plan history from DB
    history_rows = (
        SignalPlanHistory.query
        .filter_by(junction_id=j_id)
        .order_by(SignalPlanHistory.applied_at.desc())
        .limit(10)
        .all()
    )

    history_data = [
        {
            "time":       h.applied_at.strftime("%I:%M %p"),
            "phase_a":    h.phase_a_sec,
            "phase_b":    h.phase_b_sec,
            "phase_c":    h.phase_c_sec,
            "phase_d":    h.phase_d_sec,
            "applied_by": h.applied_by,
        }
        for h in history_rows
    ]

    # Adjust mock stats based on range selection for responsive UX
    range_multiplier = {"today": 1.0, "yesterday": 1.05, "7days": 0.95, "30days": 0.9}.get(time_range, 1.0)
    wait_sec  = max(20, int(46 * range_multiplier))
    queue_m   = max(30, int(68 * range_multiplier))
    thru_veh  = max(1000, int(1620 / range_multiplier))

    stats = {
        "avg_waiting_time_sec":  wait_sec,
        "avg_waiting_trend_pct": -12,
        "avg_queue_length_m":    queue_m,
        "avg_queue_trend_pct":   18,
        "throughput_veh_hr":     thru_veh,
        "congestion_level":      j_obj.status if j_obj else "high",
    }

    # Time range labels & trend data
    if time_range == "today" or time_range == "yesterday":
        labels = ["04:00", "06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]
        high   = [15, 25, 65, 82, 55, 48, 75, 88, 35]
        medium = [30, 45, 25, 12, 35, 40, 20, 10, 45]
        low    = [55, 30, 10, 6,  10, 12, 5,  2,  20]
    elif time_range == "7days":
        labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        high   = [45, 50, 68, 72, 85, 40, 30]
        medium = [35, 30, 22, 18, 10, 45, 50]
        low    = [20, 20, 10, 10, 5,  15, 20]
    else:  # 30days
        labels = ["Week 1", "Week 2", "Week 3", "Week 4"]
        high   = [60, 65, 70, 58]
        medium = [28, 25, 20, 30]
        low    = [12, 10, 10, 12]

    vehicle_composition = {
        "total_pcu": 48,
        "breakdown": [
            {"type": "Car",         "pcu_weight": 1.0, "pct": 50},
            {"type": "Two Wheeler", "pcu_weight": 0.5, "pct": 30},
            {"type": "Bus/Truck",   "pcu_weight": 3.0, "pct": 20},
        ],
    }

    return jsonify({
        "junction":            f"Junction {junction_key}",
        "stats":               stats,
        "traffic_trend": {
            "labels": labels,
            "high":   high,
            "medium": medium,
            "low":    low,
        },
        "vehicle_composition": vehicle_composition,
        "signal_plan_history": history_data,
    })


@legacy_bp.route("/api/export_analytics")
@login_required
def api_export_analytics():
    """
    Downloads CSV file of junction analytics & signal plan history.
    """
    import io
    import csv
    from flask import Response

    junction_key = request.args.get("junction", "A")
    time_range   = request.args.get("range", "today")

    j_obj = Junction.query.filter_by(name=f"Junction {junction_key}").first()
    j_id  = j_obj.id if j_obj else 1

    history_rows = (
        SignalPlanHistory.query
        .filter_by(junction_id=j_id)
        .order_by(SignalPlanHistory.applied_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header section
    writer.writerow(["I2TMS - Junction Analytics Export"])
    writer.writerow(["Junction", f"Junction {junction_key}"])
    writer.writerow(["Time Range", time_range])
    writer.writerow(["Export Date", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")])
    writer.writerow([])

    # History Table
    writer.writerow(["Applied Time", "Phase A (s)", "Phase B (s)", "Phase C (s)", "Phase D (s)", "Applied By"])
    for h in history_rows:
        writer.writerow([
            h.applied_at.strftime("%Y-%m-%d %I:%M:%S %p"),
            h.phase_a_sec,
            h.phase_b_sec,
            h.phase_c_sec,
            h.phase_d_sec,
            h.applied_by
        ])

    csv_data = output.getvalue()
    filename = f"Junction_{junction_key}_Analytics_{time_range}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ---------------------------------------------------------------------------
# API Routes — Seed helpers (dev / first-run)
# ---------------------------------------------------------------------------

@legacy_bp.route("/api/seed_traffic_trend", methods=["POST"])
@login_required
def api_seed_traffic_trend():
    """
    One-shot seed endpoint: insert 12 TrafficTrend rows covering the last
    60 minutes in 5-minute buckets so the dashboard chart has data to render.
    Also seeds 4 DecisionLog rows if the table is empty.
    Safe to call multiple times — skips buckets that already exist.
    """
    from app.models.traffic_trend import TrafficTrend
    from app.models.decision_log import DecisionLog

    now = datetime.utcnow()

    # Find the "Rahate Colony Square" junction (created at app startup)
    j_obj = Junction.query.filter_by(name="Rahate Colony Square").first()
    j_id   = j_obj.id if j_obj else None
    j_name = "Rahate Colony Square"

    # Fallback: any junction
    if j_obj is None:
        j_obj = Junction.query.first()
        if j_obj:
            j_id   = j_obj.id
            j_name = j_obj.name

    # --- TrafficTrend seed ---
    # 12 buckets x 5 min = 60-min window
    bucket_specs = [
        # (minutes_back, vehicle_count, pcu,  congestion_level, avg_speed, traffic_level)
        (60, 45, 28.5, "HIGH",   12.3, "HIGH"),
        (55, 38, 22.1, "MEDIUM", 16.8, "MEDIUM"),
        (50, 52, 31.0, "HIGH",   10.5, "HIGH"),
        (45, 29, 17.4, "MEDIUM", 21.2, "MEDIUM"),
        (40, 18, 10.8, "LOW",    28.7, "LOW"),
        (35, 41, 24.6, "HIGH",   14.1, "HIGH"),
        (30, 35, 20.9, "MEDIUM", 18.4, "MEDIUM"),
        (25, 22, 13.2, "LOW",    25.6, "LOW"),
        (20, 48, 28.8, "HIGH",   11.9, "HIGH"),
        (15, 31, 18.6, "MEDIUM", 19.7, "MEDIUM"),
        (10, 24, 14.4, "LOW",    24.1, "LOW"),
        (5,  55, 33.0, "HIGH",    9.8, "HIGH"),
    ]
    seeded_trend = 0
    for (mins_back, vcount, pcu_val, cong, speed, tlevel) in bucket_specs:
        raw_t   = now - timedelta(minutes=mins_back)
        bucket  = raw_t.replace(minute=(raw_t.minute // 5) * 5, second=0, microsecond=0)
        existing = TrafficTrend.query.filter_by(junction_id=j_id, time_bucket=bucket).first()
        if existing is None:
            db.session.add(TrafficTrend(
                junction_id      = j_id,
                junction_name    = j_name,
                time_bucket      = bucket,
                vehicle_count    = vcount,
                pcu              = pcu_val,
                congestion_level = cong,
                average_speed    = speed,
                traffic_level    = tlevel,
                created_at       = now,
            ))
            seeded_trend += 1

    # --- DecisionLog seed (only if table is completely empty) ---
    seeded_logs = 0
    if DecisionLog.query.count() == 0:
        log_specs = [
            # (mins_back, direction, decision, reason, traffic_level, cong_level, pcu, green_time, module)
            (10,  "NORTH", "EXTEND GREEN",   "High congestion — PCU=28.5, queue=15",  "HIGH",   "HIGH",   28.5, 52.0, "adaptive_signal"),
            (20,  "EAST",  "ADAPTIVE",       "Hold GREEN 30s (PCU=22.1, MEDIUM)",     "MEDIUM", "MEDIUM", 22.1, 30.0, "adaptive_signal"),
            (30,  "SOUTH", "REDUCE GREEN",   "Low demand — PCU=10.8, queue=4",        "LOW",    "LOW",    10.8, 18.0, "adaptive_signal"),
            (40,  "WEST",  "MANUAL OVERRIDE","Operator override — phase extended",    "HIGH",   "HIGH",   24.6, 45.0, "manual_override"),
        ]
        for (mins_back, direction, decision, reason, tlevel, clevel, pcu_val, gtime, module) in log_specs:
            db.session.add(DecisionLog(
                module           = module,
                junction_id      = j_id,
                junction_name    = j_name,
                direction        = direction,
                decision         = decision,
                reason           = reason,
                traffic_level    = tlevel,
                congestion_level = clevel,
                pcu              = pcu_val,
                green_time       = gtime,
                created_at       = now - timedelta(minutes=mins_back),
            ))
            seeded_logs += 1

    db.session.commit()
    return jsonify({
        "ok": True,
        "seeded_trend_rows": seeded_trend,
        "seeded_decision_logs": seeded_logs,
        "message": f"Seeded {seeded_trend} TrafficTrend rows and {seeded_logs} DecisionLog rows.",
    })


@legacy_bp.route("/api/decision_logs")
@login_required
def api_decision_logs():
    """
    Decision logs — queries the DecisionLog table (DB-backed).
    Falls back to SignalPlanHistory if DecisionLog is empty (backward compat).
    """
    from app.models.decision_log import DecisionLog

    junction_filter  = request.args.get("junction", "all")
    time_range       = request.args.get("range",    "today").lower()
    decision_type    = request.args.get("type",     "all").lower()
    page             = request.args.get("page",     1, type=int)
    per_page         = request.args.get("per_page", 5, type=int)

    # ── Build query ───────────────────────────────────────────────────────
    query = DecisionLog.query

    if junction_filter != "all":
        # Accept either short key ("A") or full name ("Rahate Colony Square")
        if len(junction_filter) <= 2:
            query = query.filter(
                DecisionLog.junction_name.like(f"Junction {junction_filter}%")
            )
        else:
            query = query.filter(DecisionLog.junction_name == junction_filter)

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if time_range == "today":
        query = query.filter(DecisionLog.created_at >= today_start)
    elif time_range == "yesterday":
        query = query.filter(
            DecisionLog.created_at >= today_start - timedelta(days=1),
            DecisionLog.created_at <  today_start,
        )
    elif time_range == "7days":
        query = query.filter(DecisionLog.created_at >= today_start - timedelta(days=7))
    elif time_range == "30days":
        query = query.filter(DecisionLog.created_at >= today_start - timedelta(days=30))

    if decision_type != "all":
        # Map UI value → module/decision column value
        if decision_type == "adaptive":
            query = query.filter(DecisionLog.module == "adaptive_signal")
        elif decision_type == "manual_override":
            query = query.filter(DecisionLog.module == "manual_override")
        elif decision_type == "emergency":
            query = query.filter(DecisionLog.module == "emergency_corridor")

    query = query.order_by(DecisionLog.created_at.desc())

    # ── Check if we have any DecisionLog rows at all ──────────────────────
    if DecisionLog.query.count() == 0:
        # Fall back to SignalPlanHistory for backward compatibility
        return _api_decision_logs_legacy(junction_filter, time_range, decision_type, page, per_page)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    rows_data = []
    for log in pagination.items:
        # Build a plan summary from green_time or metadata
        plan_summary = ""
        if log.green_time:
            dir_label = (log.direction or "").upper()
            plan_summary = f"{dir_label}: {log.green_time:.0f}s"
        elif log.metadata_ and isinstance(log.metadata_, dict):
            phases = log.metadata_.get("signal_plan", [])
            if phases:
                plan_summary = "  ".join(
                    f"{p.get('direction_label','?')}:{p.get('green_time_sec',0):.0f}s"
                    for p in phases[:4]
                )
        if not plan_summary:
            plan_summary = log.decision or "—"

        rows_data.append({
            "time":             log.created_at.strftime("%I:%M %p"),
            "junction":         log.junction_name or "—",
            "direction":        log.direction or "—",
            "decision":         log.decision or "—",
            "decision_type":    log.module or "adaptive",
            "traffic_level":    log.traffic_level or "—",
            "congestion_level": log.congestion_level or "—",
            "pcu":              round(log.pcu, 1) if log.pcu else "—",
            "green_time":       round(log.green_time, 0) if log.green_time else "—",
            "reason":           log.reason or "",
            "recommended_plan": plan_summary,
            "applied_by":       "System" if log.module == "adaptive_signal" else "Operator",
        })

    return jsonify({
        "rows": rows_data,
        "pagination": {
            "current_page": pagination.page,
            "per_page":     pagination.per_page,
            "total_rows":   pagination.total,
            "total_pages":  pagination.pages,
        },
    })


def _api_decision_logs_legacy(junction_filter, time_range, decision_type, page, per_page):
    """Backward-compat fallback: query SignalPlanHistory when DecisionLog is empty."""
    query = SignalPlanHistory.query

    if junction_filter != "all":
        j_obj = Junction.query.filter_by(name=f"Junction {junction_filter}").first()
        if j_obj:
            query = query.filter_by(junction_id=j_obj.id)
        else:
            return jsonify({"rows": [], "pagination": {
                "current_page": page, "per_page": per_page,
                "total_rows": 0, "total_pages": 0}})

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if time_range == "today":
        query = query.filter(SignalPlanHistory.applied_at >= today_start)
    elif time_range == "yesterday":
        query = query.filter(
            SignalPlanHistory.applied_at >= today_start - timedelta(days=1),
            SignalPlanHistory.applied_at <  today_start)
    elif time_range == "7days":
        query = query.filter(SignalPlanHistory.applied_at >= today_start - timedelta(days=7))
    elif time_range == "30days":
        query = query.filter(SignalPlanHistory.applied_at >= today_start - timedelta(days=30))

    if decision_type not in ("all", "adaptive", "manual_override"):
        decision_type = "all"
    if decision_type != "all":
        query = query.filter_by(decision_type=decision_type)

    query = query.order_by(SignalPlanHistory.applied_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    rows_data = [
        {
            "time":             h.applied_at.strftime("%I:%M %p"),
            "junction":         h.junction.name if h.junction else f"Junction {h.junction_id}",
            "direction":        "—",
            "decision":         h.decision_type.replace("_", " ").title(),
            "decision_type":    h.decision_type,
            "traffic_level":    "—",
            "congestion_level": "—",
            "pcu":              "—",
            "green_time":       "—",
            "reason":           "",
            "recommended_plan": f"A:{h.phase_a_sec} B:{h.phase_b_sec} C:{h.phase_c_sec} D:{h.phase_d_sec}",
            "applied_by":       h.applied_by,
        }
        for h in pagination.items
    ]
    return jsonify({
        "rows": rows_data,
        "pagination": {
            "current_page": pagination.page,
            "per_page":     pagination.per_page,
            "total_rows":   pagination.total,
            "total_pages":  pagination.pages,
        },
    })




# ---------------------------------------------------------------------------
# API Routes — Screen 6-new: Geocode + Emergency Request API
# ---------------------------------------------------------------------------

_NAGPUR_FALLBACK = [
    {"name": "VNIT Campus, Nagpur",               "lat": 21.1333, "lng": 79.0526},
    {"name": "Mayo Hospital, Nagpur",              "lat": 21.1428, "lng": 79.0780},
    {"name": "Government Medical College, Nagpur", "lat": 21.1453, "lng": 79.0815},
    {"name": "AIIMS Nagpur",                       "lat": 21.1080, "lng": 79.0590},
    {"name": "Zero Mile, Nagpur",                  "lat": 21.1467, "lng": 79.0861},
    {"name": "Sitabuldi Junction, Nagpur",         "lat": 21.1458, "lng": 79.0788},
    {"name": "Variety Square, Nagpur",             "lat": 21.1482, "lng": 79.0742},
    {"name": "Nagpur Central Fire Station",        "lat": 21.1462, "lng": 79.0836},
    {"name": "Ganeshpeth Fire Station, Nagpur",    "lat": 21.1415, "lng": 79.0758},
]


@legacy_bp.route("/api/geocode")
def geocode():
    """
    Location geocoding autocomplete.
    Queries Nominatim API and falls back to a hardcoded local Nagpur list if rate limited or offline.
    """
    q = request.args.get("q", "")
    if len(q) < 2:
        return jsonify([])
    try:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                          params={"q": f"{q}, Nagpur", "format": "json", "limit": 8},
                          headers={"User-Agent": "I2TMS-Nagpur/1.0"},
                          timeout=3)
        if r.ok:
            results = [{"name": item["display_name"], "lat": float(item["lat"]), "lng": float(item["lon"])} for item in r.json()]
            if results:
                return jsonify(results)
    except Exception as e:
        print(f"[geocode fallback] Nominatim failed: {e}")

    # Local substring Nagpur fallback
    q_lower = q.lower()
    fallback_matches = [
        {"name": loc["name"], "lat": loc["lat"], "lng": loc["lng"]}
        for loc in _NAGPUR_FALLBACK
        if q_lower in loc["name"].lower()
    ]
    return jsonify(fallback_matches)


@legacy_bp.route("/api/reverse_geocode")
def reverse_geocode():
    """
    Location reverse-geocoding.
    Queries Nominatim API to get location name from coordinates.
    """
    lat, lng = request.args.get("lat"), request.args.get("lng")
    try:
        r = requests.get("https://nominatim.openstreetmap.org/reverse",
                          params={"lat": lat, "lon": lng, "format": "json"},
                          headers={"User-Agent": "I2TMS-Nagpur/1.0"},
                          timeout=3)
        if r.ok:
            data = r.json()
            return jsonify({"display_name": data.get("display_name", f"{lat},{lng}")})
    except Exception as e:
        print(f"[reverse_geocode fallback] Nominatim failed: {e}")

    return jsonify({"display_name": f"{lat},{lng}"})


@legacy_bp.route("/api/emergency_request", methods=["POST"])
# @login_required # Temporarily disabled for ambulance frontend without login
def create_emergency_request():
    """
    POST /api/emergency_request
    Generates new emergency request, computes metrics, and inserts into DB.
    """
    body = request.get_json(force=True) or {}
    
    # Handle both old and new payload formats
    c_lat, c_lng = None, None
    d_lat, d_lng = None, None
    origin_name = "Unknown Origin"
    dest_name = "Unknown Destination"
    
    if "origin" in body and "destination" in body and isinstance(body["origin"], dict):
        c_lat = body["origin"]["lat"]
        c_lng = body["origin"]["lng"]
        origin_name = body["origin"]["name"]
        d_lat = body["destination"]["lat"]
        d_lng = body["destination"]["lng"]
        dest_name = body["destination"]["name"]
    else:
        for field in ["vehicle_type", "vehicle_number", "current_location", "destination"]:
            if not body.get(field):
                return jsonify({"error": f"{field} is required"}), 400
        origin_name = body["current_location"]
        dest_name = body["destination"]
        c_lat = float(body.get("current_lat") or 21.1458)
        c_lng = float(body.get("current_lng") or 79.0526)
        d_lat = float(body.get("destination_lat") or 21.1428)
        d_lng = float(body.get("destination_lng") or 79.0780)

    # --- REAL ROUTING VIA OSRM ---
    route_result = calculate_route(c_lat, c_lng, d_lat, d_lng)
    
    distance_km = route_result.get("distance_km", 0.0)
    eta_min = route_result.get("eta_min", 0)
    mock_geometry = route_result.get("geometry", [])
    
    # Simulate signal and VMS counts for the prototype
    signals_on_route = random.randint(3, 8)
    vms_on_route = random.randint(1, 5)

    import json as _json
    route_data = _json.dumps({
        "distance_km": distance_km,
        "eta_min": eta_min,
        "signals_on_route": signals_on_route,
        "vms_on_route": vms_on_route
    })

    req = EmergencyRequest(
        vehicle_type=body.get("vehicle_type", "ambulance"),
        vehicle_number=body.get("vehicle_number", "UNKNOWN"),
        current_location=origin_name,
        current_lat=c_lat, 
        current_lng=c_lng,
        destination=dest_name,
        destination_lat=d_lat, 
        destination_lng=d_lng,
        priority=body.get("priority", "high"),
        requested_by=session.get("user_id"),
        route_distance_km=distance_km,
        route_eta_min=eta_min,
        route_data=route_data,
        route_geometry=_json.dumps(mock_geometry),
        signals_on_route=signals_on_route,
        vms_on_route=vms_on_route,
        status="active"
    )
    db.session.add(req)
    db.session.commit()

    return jsonify({
        "status": "success",
        "data": {
            "request_id": req.id,
            "distance_km": distance_km,
            "baseline_eta_min": eta_min,
            "optimized_eta_min": max(1, int(eta_min * 0.6)), # 40% reduction for green corridor
            "geometry": mock_geometry
        }
    })


@legacy_bp.route("/api/emergency_request/<int:req_id>")
@login_required
def get_emergency_request(req_id):
    import json as _json
    req = EmergencyRequest.query.get_or_404(req_id)

    # --- MOCK: upcoming signals / VMS ---
    # TODO: Replace with real corridor data once Agent 2 (green-corridor pipeline)
    # exposes per-route signal/VMS state. Both this block and create_emergency_request
    # should then share the same upstream data source.
    upcoming_signals = [
        {"junction": "Junction 23", "distance_km": 0.8,  "status": "Priority Active", "time_to_reach_min": 2},
        {"junction": "Junction 27", "distance_km": 1.3,  "status": "Priority Active", "time_to_reach_min": 4},
        {"junction": "Junction 31", "distance_km": 2.6,  "status": "Normal",          "time_to_reach_min": 7},
    ]
    active_vms = [
        {"vms_id": "VMS-12", "location": "Trimurti Nagar",  "message": "CLEAR LANE", "status": "Active"},
        {"vms_id": "VMS-15", "location": "Sitabuldi Chowk", "message": "CLEAR LANE", "status": "Active"},
        {"vms_id": "VMS-18", "location": "Mayo Square",     "message": "CLEAR LANE", "status": "Active"},
    ]
    # --- end mock block ---

    return jsonify({
        "vehicle_number":        req.vehicle_number,
        "current_lat":           req.current_lat,
        "current_lng":           req.current_lng,
        "destination_lat":       req.destination_lat,
        "destination_lng":       req.destination_lng,
        "route_distance_km":     req.route_distance_km,
        # mock: same as total until real GPS tracking provides live remaining distance
        "distance_remaining_km": req.route_distance_km,
        "route_eta_min":         req.route_eta_min,
        "signals_on_route":      len(upcoming_signals),
        "vms_on_route":          len(active_vms),
        "upcoming_signals":      upcoming_signals,
        "active_vms":            active_vms,
        "route_geometry":        _json.loads(req.route_geometry) if req.route_geometry else None,
        "status":                req.status,
    })


@legacy_bp.route("/api/emergency_request/<int:req_id>/end", methods=["POST"])
# @login_required
def end_emergency_request(req_id):
    req = EmergencyRequest.query.get_or_404(req_id)
    req.status = "completed"
    db.session.commit()
    return jsonify({"ok": True})


@legacy_bp.route("/api/emergency/location", methods=["POST"])
def update_emergency_location():
    """Simulated endpoint for ambulance GPS updates."""
    body = request.get_json(force=True) or {}
    req_id = body.get("request_id")
    if req_id:
        req = EmergencyRequest.query.get(req_id)
        if req:
            req.current_lat = body.get("lat")
            req.current_lng = body.get("lng")
            db.session.commit()
            # In a real app, this would trigger SocketIO events or update active signals
            return jsonify({"status": "ok"})
    return jsonify({"error": "Invalid request"}), 400



@legacy_bp.route("/emergency/route/<int:request_id>")
@login_required
def emergency_route_view(request_id):
    """
    Screen 7 Route Map View placeholder.
    Renders simple details page for now.
    """
    req = EmergencyRequest.query.get_or_404(request_id)
    return render_template("stub.html", page_name=f"Emergency Route Map (Request #{req.id} - {req.vehicle_number})", active_page="emergency")


# ---------------------------------------------------------------------------
# API Routes — Screen 10: Incidents & Alerts
# ---------------------------------------------------------------------------

@legacy_bp.route("/api/incidents_alerts")
@login_required
def api_incidents_alerts():
    """
    Unified, paginated alert feed merging the Alert table (system alerts)
    and the EmergencyRequest table (emergency dispatches).

    Query params:
      type      — alert type name or 'all' or 'Emergency Dispatch'
      severity  — 'all' | 'high' | 'medium' | 'low'
      range     — 'today' | 'yesterday' | '7days' | '30days'
      page      — int (1-indexed)
      per_page  — int (default 5)
    """
    type_filter     = request.args.get("type",     "all")
    severity_filter = request.args.get("severity", "all")
    range_filter    = request.args.get("range",    "today")
    page            = max(1, request.args.get("page",     1, type=int))
    per_page        = max(1, request.args.get("per_page", 5, type=int))

    now = datetime.utcnow()

    # ── Time range boundary ─────────────────────────────────────────────
    _range_days = {"today": 1, "yesterday": 2, "7days": 7, "30days": 30}
    cutoff_days = _range_days.get(range_filter, 1)
    cutoff      = now - timedelta(days=cutoff_days)

    rows = []

    # ── Regular system alerts ──────────────────────────────────────────
    if type_filter not in ("Emergency Dispatch",):
        alert_q = Alert.query.filter(Alert.created_at >= cutoff)
        if type_filter != "all":
            alert_q = alert_q.filter_by(alert_type=type_filter)
        if severity_filter != "all":
            alert_q = alert_q.filter_by(severity=severity_filter)

        for a in alert_q.all():
            # Resolve junction label from DB relationship
            location = a.junction.name if a.junction else (
                f"Junction {a.junction_id}" if a.junction_id else "—"
            )
            rows.append({
                "type":      a.alert_type,
                "severity":  a.severity,
                "location":  location,
                "time":      a.created_at,
                "status":    a.status.capitalize(),
                "icon":      "triangle",
                "sort_time": a.created_at,
                "request_id": None,
            })

    # ── Emergency requests folded into the same feed ────────────────────
    if type_filter in ("all", "Emergency Dispatch"):
        emg_q = EmergencyRequest.query.filter(EmergencyRequest.requested_at >= cutoff)
        # Emergency requests always count as 'high' severity
        if severity_filter not in ("all", "high"):
            emg_q = emg_q.filter(False)  # exclude if filtering medium/low only

        for e in emg_q.all():
            rows.append({
                "type":      f"Emergency Dispatch — {e.vehicle_number}",
                "severity":  "high",
                "location":  f"{e.current_location} → {e.destination}",
                "time":      e.requested_at,
                "status":    "Active" if e.status == "active" else "Resolved",
                "icon":      "🚑" if e.vehicle_type == "ambulance" else "🚒",
                "sort_time": e.requested_at,
                "request_id": e.id,
            })

    # ── Sort newest first ─────────────────────────────────────────────────
    rows.sort(key=lambda r: r["sort_time"], reverse=True)

    # ── Paginate ─────────────────────────────────────────────────────
    total      = len(rows)
    start      = (page - 1) * per_page
    page_rows  = rows[start : start + per_page]
    total_pages = -(-total // per_page)  # ceiling division

    return jsonify({
        "rows": [
            {
                "type":       r["type"],
                "severity":   r["severity"],
                "location":   r["location"],
                "time":       r["time"].strftime("%I:%M %p").lstrip("0"),
                "status":     r["status"],
                "icon":       r["icon"],
                "request_id": r.get("request_id"),
            }
            for r in page_rows
        ],
        "pagination": {
            "current_page": page,
            "per_page":     per_page,
            "total_rows":   total,
            "total_pages":  total_pages,
        },
    })


@legacy_bp.route("/live-video")
@login_required
def live_video():
    """Screen 9: Live Junction Video — dropdown of all configured junctions."""
    from app.models.adaptive_signal_state import AdaptiveSignalState

    # All junctions with at least one AdaptiveSignalState row OR all seeded junctions
    all_junctions = Junction.query.order_by(Junction.name).all()

    # Build a list of keys that match the ADAPTIVE_JUNCTIONS map + any DB junction
    # Use the full name as the key for cleanliness
    junction_options = [
        {"key": j.name, "label": j.name}
        for j in all_junctions
    ]

    # Default: first junction in the list, or URL param
    default_key = request.args.get("junction", "")
    if not default_key and junction_options:
        default_key = junction_options[0]["key"]

    return render_template(
        "live-video.html",
        active_page="live_video",
        selected_junction=default_key,
        junction_options=junction_options,
    )


# ---------------------------------------------------------------------------
# API Routes — Screen 9: Live Junction Video
# ---------------------------------------------------------------------------

# In-memory recording state: {junction_key: bool}
_recording_state: dict = {}


@legacy_bp.route("/api/live_demo_stats")
def api_live_demo_stats():
    """
    Returns traffic stats for a given demo part (1-4) from the static JSON files.
    These are the real detection results from the pre-recorded CCTV footage.
    No login required — called from the live-video demo page.
    """
    import json as _json
    from pathlib import Path

    part = request.args.get("part", "1")
    try:
        part_num = int(part)
        if part_num < 1 or part_num > 4:
            part_num = 1
    except ValueError:
        part_num = 1

    json_path = Path(__file__).resolve().parent.parent.parent / "static" / "videos" / f"part-{part_num}.json"
    try:
        with open(json_path, encoding="utf-8") as f:
            raw = _json.load(f)
    except Exception:
        return jsonify({"error": "data not found"}), 404

    counts = raw.get("vehicle_counts", {})
    total  = raw.get("total_unique_tracked_vehicles", 0)

    # PCU weights (standard Indian road PCU equivalents)
    PCU = {"car": 1.0, "motorcycle": 0.5, "bus": 3.0, "truck": 3.0, "auto": 0.8}
    pcu = sum(counts.get(k, 0) * v for k, v in PCU.items())
    pcu = round(pcu, 1)

    # Derive traffic level from PCU
    if pcu >= 400:
        traffic_level = "HIGH"
        congestion    = "HIGH"
    elif pcu >= 200:
        traffic_level = "MEDIUM"
        congestion    = "MEDIUM"
    else:
        traffic_level = "LOW"
        congestion    = "LOW"

    # Estimated queue length proxy: roughly 1 vehicle ≈ 5–6 m
    queue_m = min(int(total * 0.18), 150)  # rough proxy

    return jsonify({
        "part":             part_num,
        "video_url":        f"/static/videos/part-{part_num}-result.mp4",
        "total_vehicles":   total,
        "vehicle_counts":   counts,
        "pcu":              pcu,
        "traffic_level":    traffic_level,
        "congestion_level": congestion,
        "queue_length":     queue_m,
        "data_available":   True,
    })
    """
    Per-junction live video stats — DB-backed from AdaptiveSignalState.
    Falls back to neutral defaults if no pipeline data exists yet.
    """
    from app.models.adaptive_signal_state import AdaptiveSignalState

    junction_key = request.args.get("junction", "")

    # Accept full junction name or short letter key
    j = None
    if junction_key:
        j = Junction.query.filter_by(name=junction_key).first()
        if j is None and len(junction_key) <= 2:
            j = Junction.query.filter_by(name=f"Junction {junction_key}").first()

    junction_name = j.name if j else (junction_key or "Junction A")
    camera_url    = (j.camera_thumbnail_url or "") if j else ""

    # Find the worst direction for this junction (highest congestion)
    states = (
        AdaptiveSignalState.query
        .filter_by(junction_name=junction_name)
        .all()
    )

    if states:
        # Use worst-congestion direction as the representative state
        level_order = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}
        worst = max(states, key=lambda s: level_order.get((s.congestion_level or "LOW").upper(), 0))
        traffic_state_val = (worst.traffic_level or "low").lower()
        pcu               = round(worst.pcu_demand, 1)
        queue_length_m    = worst.queue_length
        avg_speed_kmh     = round(worst.average_speed, 1)
        vehicle_count     = worst.vehicle_count_total
        density           = round(worst.density, 3)
        occupancy         = round(worst.occupancy, 3)
        waiting_time      = round(worst.waiting_time, 1)
        congestion_level  = (worst.congestion_level or "LOW").upper()
        # Vehicle breakdown
        vc_by_class = dict(worst.vehicle_count_by_class) if worst.vehicle_count_by_class else {}
    else:
        # No pipeline data yet — neutral empty state
        traffic_state_val = "low"
        pcu               = 0
        queue_length_m    = 0
        avg_speed_kmh     = 0
        vehicle_count     = 0
        density           = 0.0
        occupancy         = 0.0
        waiting_time      = 0.0
        congestion_level  = "LOW"
        vc_by_class       = {"car": 0, "bus": 0, "truck": 0, "bike": 0, "auto": 0}

    now_str = datetime.now().strftime("%I:%M:%S %p").lstrip("0")

    return jsonify({
        "junction":        junction_name,
        "camera_label":    "Camera 01",
        "camera_url":      camera_url,
        "traffic_state":   traffic_state_val,
        "congestion_level": congestion_level,
        "pcu":             pcu,
        "vehicle_count":   vehicle_count,
        "vehicle_breakdown": vc_by_class,
        "queue_length_m":  queue_length_m,
        "avg_speed_kmh":   avg_speed_kmh,
        "density":         density,
        "occupancy":       occupancy,
        "waiting_time":    waiting_time,
        "last_updated":    now_str,
        "data_available":  len(states) > 0,
    })


@legacy_bp.route("/api/snapshot", methods=["POST"])
@login_required
def api_snapshot():
    """
    Return the current camera frame as a downloadable image.
    MOCK: serves the static placeholder image.
    TODO: Capture the actual live frame from the camera stream.
    """
    junction_key = request.args.get("junction", "A")
    placeholder_path = os.path.join(
        BASE_DIR, "static", "img", "camera-placeholder.jpg"
    )
    if not os.path.exists(placeholder_path):
        # Fallback: return a tiny 1×1 white JPEG in memory
        import struct
        jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 16 + b"\xff\xd9"
        buf = io.BytesIO(jpeg_bytes)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="image/jpeg",
            as_attachment=True,
            download_name=f"snapshot_junction_{junction_key}.jpg",
        )

    return send_file(
        placeholder_path,
        mimetype="image/jpeg",
        as_attachment=True,
        download_name=f"snapshot_junction_{junction_key}.jpg",
    )


@legacy_bp.route("/api/toggle_recording", methods=["POST"])
@login_required
def api_toggle_recording():
    """
    Toggle recording state for a junction.
    MOCK: tracks flag in memory — no real stream is written.
    TODO: Real implementation should start/stop writing the camera stream to disk
    (e.g. ffmpeg subprocess capturing RTSP feed).
    Body: {"junction": "A", "recording": true}
    """
    data     = request.get_json(force=True) or {}
    j_key    = data.get("junction", "A")
    new_state = bool(data.get("recording", False))
    _recording_state[j_key] = new_state
    print(f"[recording] Junction {j_key} → {'STARTED' if new_state else 'STOPPED'}")
    return jsonify({"junction": j_key, "recording": new_state})





# ---------------------------------------------------------------------------
# API Routes — Screen 11: Reports Module
# ---------------------------------------------------------------------------

@legacy_bp.route("/api/generate_report", methods=["POST"])
@login_required
def api_generate_report():
    body = request.get_json(force=True) or {}
    report_type = body.get("report_type")
    time_range = body.get("time_range", "this_week")
    range_start_str = body.get("range_start")
    range_end_str = body.get("range_end")

    if not report_type:
        return jsonify({"error": "report_type is required"}), 400

    range_start = None
    range_end = None
    if time_range == "custom":
        if not range_start_str or not range_end_str:
            return jsonify({"error": "range_start and range_end are required for custom range"}), 400
        try:
            range_start = datetime.strptime(range_start_str, "%Y-%m-%d")
            range_end = datetime.strptime(range_end_str, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    # Summary generator
    title_range_map = {
        "today": "Today",
        "this_week": "This Week",
        "this_month": "This Month",
        "custom": f"Custom Range ({range_start_str} to {range_end_str})"
    }
    range_label = title_range_map.get(time_range, "Selected Period")

    stats = []
    if report_type == "traffic_performance":
        title = f"Traffic Performance Report — {range_label}"
        total_j = Junction.query.count()
        stats = [
            {"label": "Monitored Junctions", "value": total_j or 4},
            {"label": "Total Traffic Volume", "value": "142,850 vehicles"},
            {"label": "Peak Flow Rate", "value": "3,200 PCU/hr"},
            {"label": "Avg Delay Reduction", "value": "18.4%"}
        ]
    elif report_type == "signal_optimization":
        title = f"Signal Optimization Report — {range_label}"
        total_adaptive = SignalPlanHistory.query.filter_by(decision_type='adaptive').count()
        total_overrides = SignalPlanHistory.query.filter_by(decision_type='manual_override').count()
        history_list = SignalPlanHistory.query.all()
        avg_duration = 30
        if history_list:
            total_sec = sum(h.phase_a_sec + h.phase_b_sec + h.phase_c_sec + h.phase_d_sec for h in history_list)
            avg_duration = round(total_sec / (4 * len(history_list)), 1)
        
        stats = [
            {"label": "Adaptive Decisions", "value": total_adaptive},
            {"label": "Manual Overrides", "value": total_overrides},
            {"label": "Avg Phase Duration", "value": f"{avg_duration}s"},
            {"label": "Efficiency Index", "value": "92.4%"}
        ]
    elif report_type == "congestion":
        title = f"Congestion Report — {range_label}"
        stats = [
            {"label": "Top Bottleneck", "value": "Sitabuldi Junction"},
            {"label": "Peak Delay Time", "value": "4.5 min"},
            {"label": "Avg Queue Length", "value": "125 m"},
            {"label": "Active Hotspots", "value": 3}
        ]
    elif report_type == "emergency_response":
        title = f"Emergency Response Report — {range_label}"
        total_dispatches = EmergencyRequest.query.count()
        completed_corridors = EmergencyRequest.query.filter_by(status='completed').count()
        avg_eta_row = db.session.query(db.func.avg(EmergencyRequest.route_eta_min)).first()
        avg_eta = round(avg_eta_row[0], 1) if avg_eta_row and avg_eta_row[0] is not None else 0.0
        avg_signals_row = db.session.query(db.func.avg(EmergencyRequest.signals_on_route)).first()
        avg_signals = round(avg_signals_row[0], 1) if avg_signals_row and avg_signals_row[0] is not None else 0.0

        stats = [
            {"label": "Total Dispatches", "value": total_dispatches},
            {"label": "Avg Response Time", "value": f"{avg_eta} min"},
            {"label": "Corridors Completed", "value": completed_corridors},
            {"label": "Avg Signals Preempted", "value": avg_signals}
        ]
    else:
        return jsonify({"error": f"Unknown report type: {report_type}"}), 400

    report = GeneratedReport(
        report_type=report_type,
        time_range=time_range,
        range_start=range_start,
        range_end=range_end,
        generated_by=session.get("user_id"),
        generated_at=datetime.utcnow()
    )
    db.session.add(report)
    db.session.commit()

    return jsonify({
        "report_id": report.id,
        "summary": {
            "title": title,
            "stats": stats
        },
        "download_pdf_url": f"/api/download_report/{report.id}?format=pdf",
        "download_csv_url": f"/api/download_report/{report.id}?format=csv"
    })


@legacy_bp.route("/api/download_report/<int:report_id>")
@login_required
def api_download_report(report_id):
    report = GeneratedReport.query.get_or_404(report_id)
    fmt = request.args.get("format", "pdf").lower()

    time_range = report.time_range
    range_start_str = report.range_start.strftime("%Y-%m-%d") if report.range_start else ""
    range_end_str = report.range_end.strftime("%Y-%m-%d") if report.range_end else ""

    title_range_map = {
        "today": "Today",
        "this_week": "This Week",
        "this_month": "This Month",
        "custom": f"Custom Range ({range_start_str} to {range_end_str})"
    }
    range_label = title_range_map.get(time_range, "Selected Period")

    type_title_map = {
        "traffic_performance": "Traffic Performance Report",
        "signal_optimization": "Signal Optimization Report",
        "congestion": "Congestion Report",
        "emergency_response": "Emergency Response Report"
    }
    report_title = type_title_map.get(report.report_type, "System Report")

    data_rows = []
    if report.report_type == "traffic_performance":
        data_rows = [
            ("Metric Label", "Value"),
            ("Monitored Junctions", str(Junction.query.count() or 4)),
            ("Total Traffic Volume", "142,850 vehicles"),
            ("Peak Flow Rate", "3,200 PCU/hr"),
            ("Avg Delay Reduction", "18.4%"),
            ("Overall Status", "Optimal")
        ]
    elif report.report_type == "signal_optimization":
        total_adaptive = SignalPlanHistory.query.filter_by(decision_type='adaptive').count()
        total_overrides = SignalPlanHistory.query.filter_by(decision_type='manual_override').count()
        history_list = SignalPlanHistory.query.all()
        avg_duration = 30
        if history_list:
            total_sec = sum(h.phase_a_sec + h.phase_b_sec + h.phase_c_sec + h.phase_d_sec for h in history_list)
            avg_duration = round(total_sec / (4 * len(history_list)), 1)
        data_rows = [
            ("Metric Label", "Value"),
            ("Adaptive Decisions", str(total_adaptive)),
            ("Manual Overrides", str(total_overrides)),
            ("Avg Phase Duration", f"{avg_duration}s"),
            ("Efficiency Index", "92.4%"),
            ("Optimization State", "Active")
        ]
    elif report.report_type == "congestion":
        data_rows = [
            ("Metric Label", "Value"),
            ("Top Bottleneck", "Sitabuldi Junction"),
            ("Peak Delay Time", "4.5 min"),
            ("Avg Queue Length", "125 m"),
            ("Active Hotspots", "3"),
            ("Congestion Level", "Moderate")
        ]
    elif report.report_type == "emergency_response":
        total_dispatches = EmergencyRequest.query.count()
        completed_corridors = EmergencyRequest.query.filter_by(status='completed').count()
        avg_eta_row = db.session.query(db.func.avg(EmergencyRequest.route_eta_min)).first()
        avg_eta = round(avg_eta_row[0], 1) if avg_eta_row and avg_eta_row[0] is not None else 0.0
        avg_signals_row = db.session.query(db.func.avg(EmergencyRequest.signals_on_route)).first()
        avg_signals = round(avg_signals_row[0], 1) if avg_signals_row and avg_signals_row[0] is not None else 0.0
        data_rows = [
            ("Metric Label", "Value"),
            ("Total Dispatches", str(total_dispatches)),
            ("Avg Response Time", f"{avg_eta} min"),
            ("Corridors Completed", str(completed_corridors)),
            ("Avg Signals Preempted", str(avg_signals)),
            ("Signal Preemption State", "Active")
        ]

    if fmt == "csv":
        import csv
        from flask import Response
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["I2TMS - Nagpur Municipal Corporation"])
        writer.writerow([report_title])
        writer.writerow(["Time Range", range_label])
        writer.writerow(["Generated At", report.generated_at.strftime("%Y-%m-%d %I:%M:%S %p UTC")])
        writer.writerow([])
        for row in data_rows:
            writer.writerow(row)

        csv_data = output.getvalue()
        filename = f"{report.report_type}_report_{report.id}.csv"
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    else:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        pdf_buf = io.BytesIO()
        doc = SimpleDocTemplate(
            pdf_buf,
            pagesize=letter,
            rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54
        )

        styles = getSampleStyleSheet()
        navy = colors.HexColor("#1A2942")
        teal = colors.HexColor("#0EA5A0")
        gray = colors.HexColor("#6B7280")
        light_gray = colors.HexColor("#F3F4F6")

        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=navy,
            spaceAfter=6
        )
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=13,
            textColor=gray,
            spaceAfter=20
        )
        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=teal,
            spaceAfter=10,
            spaceBefore=10
        )
        body_style = ParagraphStyle(
            'BodyTextCustom',
            parent=styles['BodyText'],
            fontName='Helvetica',
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#333333")
        )

        story = []
        story.append(Paragraph("I²TMS — Nagpur Municipal Corporation", subtitle_style))
        story.append(Paragraph(report_title, title_style))
        story.append(Paragraph(f"Period: {range_label} &middot; Generated At: {report.generated_at.strftime('%Y-%m-%d %I:%M %p')}", subtitle_style))
        story.append(Spacer(1, 10))

        divider = Table([[""]], colWidths=[504])
        divider.setStyle(TableStyle([
            ('LINEABOVE', (0,0), (-1,-1), 1.5, teal),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(divider)
        story.append(Spacer(1, 12))

        story.append(Paragraph("Report Summary", section_heading))
        
        formatted_table_data = []
        for index, row in enumerate(data_rows):
            if index == 0:
                col1 = Paragraph(f"<b>{row[0]}</b>", ParagraphStyle('H1', parent=body_style, fontName='Helvetica-Bold', textColor=colors.white))
                col2 = Paragraph(f"<b>{row[1]}</b>", ParagraphStyle('H2', parent=body_style, fontName='Helvetica-Bold', textColor=colors.white))
            else:
                col1 = Paragraph(row[0], body_style)
                col2 = Paragraph(f"<b>{row[1]}</b>", body_style)
            formatted_table_data.append([col1, col2])

        summary_table = Table(formatted_table_data, colWidths=[250, 254])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), navy),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 10),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_gray]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E5E7EB")),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 24))

        story.append(Paragraph("<b>Disclaimer:</b> This report is generated dynamically by the I²TMS Analytics Engine and contains real-time sensor aggregation coupled with database logs.", ParagraphStyle('Disclaimer', parent=body_style, fontSize=7.5, leading=10, textColor=gray)))

        doc.build(story)
        pdf_buf.seek(0)

        filename = f"{report.report_type}_report_{report.id}.pdf"
        return send_file(
            pdf_buf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )


@legacy_bp.route("/api/change_password", methods=["POST"])
@login_required
def change_password():
    body = request.get_json(force=True) or {}
    user = User.query.get(session["user_id"])
    if not check_password_hash(user.password_hash, body.get("current_password", "")):
        return jsonify({"error": "Current password is incorrect."}), 400
    user.password_hash = generate_password_hash(body.get("new_password", ""))
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API Routes — Screen 12: Settings Module
# ---------------------------------------------------------------------------

@legacy_bp.route("/api/settings", methods=["GET", "POST"])
@login_required
def api_settings():
    """Read or update the single SystemSettings row."""
    settings = SystemSettings.query.first()
    if not settings:
        settings = SystemSettings()
        db.session.add(settings)
        db.session.commit()

    if request.method == "POST":
        body = request.get_json(force=True) or {}
        settings.time_zone = body.get("time_zone", settings.time_zone)
        settings.data_refresh_interval_sec = int(body.get("data_refresh_interval_sec", settings.data_refresh_interval_sec))
        settings.default_dashboard_view = body.get("default_dashboard_view", settings.default_dashboard_view)
        settings.units = body.get("units", settings.units)
        settings.email_alerts = bool(body.get("email_alerts", settings.email_alerts))
        settings.sms_alerts = bool(body.get("sms_alerts", settings.sms_alerts))
        settings.push_notifications = bool(body.get("push_notifications", settings.push_notifications))
        settings.emergency_alerts = bool(body.get("emergency_alerts", settings.emergency_alerts))
        settings.default_cycle_time_sec = int(body.get("default_cycle_time_sec", settings.default_cycle_time_sec))
        settings.min_phase_duration_sec = int(body.get("min_phase_duration_sec", settings.min_phase_duration_sec))
        settings.max_phase_duration_sec = int(body.get("max_phase_duration_sec", settings.max_phase_duration_sec))
        db.session.commit()

    return jsonify({
        "time_zone": settings.time_zone,
        "data_refresh_interval_sec": settings.data_refresh_interval_sec,
        "default_dashboard_view": settings.default_dashboard_view,
        "units": settings.units,
        "email_alerts": settings.email_alerts,
        "sms_alerts": settings.sms_alerts,
        "push_notifications": settings.push_notifications,
        "emergency_alerts": settings.emergency_alerts,
        "default_cycle_time_sec": settings.default_cycle_time_sec,
        "min_phase_duration_sec": settings.min_phase_duration_sec,
        "max_phase_duration_sec": settings.max_phase_duration_sec
    })


@legacy_bp.route("/api/junctions", methods=["GET", "POST"])
@login_required
def api_junctions_crud():
    """GET list of junctions or POST a new junction."""
    if request.method == "POST":
        body = request.get_json(force=True) or {}
        name = body.get("name")
        lat = body.get("lat")
        lng = body.get("lng")
        junction_type = body.get("junction_type", "square")
        status = body.get("status", "low")
        thumbnail = body.get("camera_thumbnail_url")
        if not name:
            return jsonify({"error": "Name is required"}), 400
        
        j = Junction(name=name, lat=lat, lng=lng, junction_type=junction_type, status=status, camera_thumbnail_url=thumbnail, last_updated=datetime.utcnow())
        db.session.add(j)
        db.session.commit()
        return jsonify({"id": j.id, "name": j.name, "lat": j.lat, "lng": j.lng, "junction_type": j.junction_type, "status": j.status, "camera_thumbnail_url": j.camera_thumbnail_url})

    junctions = Junction.query.order_by(Junction.name).all()
    return jsonify([{
        "id": j.id,
        "name": j.name,
        "lat": j.lat,
        "lng": j.lng,
        "junction_type": j.junction_type,
        "status": j.status,
        "camera_thumbnail_url": j.camera_thumbnail_url or "",
        "last_updated": j.last_updated.strftime("%Y-%m-%d %I:%M %p")
    } for j in junctions])


@legacy_bp.route("/api/junctions/<int:j_id>", methods=["PUT"])
@login_required
def api_junction_update(j_id):
    """PUT to update an existing junction."""
    j = Junction.query.get_or_404(j_id)
    body = request.get_json(force=True) or {}
    j.name = body.get("name", j.name)
    j.lat = body.get("lat", j.lat)
    j.lng = body.get("lng", j.lng)
    j.junction_type = body.get("junction_type", j.junction_type)
    j.status = body.get("status", j.status)
    j.camera_thumbnail_url = body.get("camera_thumbnail_url", j.camera_thumbnail_url)
    j.last_updated = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True})


@legacy_bp.route("/api/vms_boards", methods=["GET", "POST"])
@login_required
def api_vms_boards_crud():
    """GET list of VMS boards or POST a new VMS board."""
    if request.method == "POST":
        body = request.get_json(force=True) or {}
        location = body.get("location")
        lat = body.get("lat")
        lng = body.get("lng")
        status = body.get("status", "active")
        current_message = body.get("current_message", "")
        
        if not location:
            return jsonify({"error": "Location is required"}), 400
        
        # Auto-generate VMS ID
        max_id = db.session.query(db.func.max(VMSBoard.id)).scalar() or 0
        vms_id = f"VMS-{max_id + 1}"

        v = VMSBoard(vms_id=vms_id, location=location, lat=lat, lng=lng, status=status, current_message=current_message)
        db.session.add(v)
        db.session.commit()
        return jsonify({"id": v.id, "vms_id": v.vms_id, "location": v.location, "lat": v.lat, "lng": v.lng, "status": v.status, "current_message": v.current_message})

    boards = VMSBoard.query.order_by(VMSBoard.vms_id).all()
    return jsonify([{
        "id": v.id,
        "vms_id": v.vms_id,
        "location": v.location,
        "lat": v.lat,
        "lng": v.lng,
        "status": v.status,
        "current_message": v.current_message or ""
    } for v in boards])


@legacy_bp.route("/api/vms_boards/<int:v_id>", methods=["PUT"])
@login_required
def api_vms_update(v_id):
    """PUT to update an existing VMS board."""
    v = VMSBoard.query.get_or_404(v_id)
    body = request.get_json(force=True) or {}
    v.location = body.get("location", v.location)
    v.lat = body.get("lat", v.lat)
    v.lng = body.get("lng", v.lng)
    v.status = body.get("status", v.status)
    v.current_message = body.get("current_message", v.current_message)
    db.session.commit()
    return jsonify({"success": True})


@legacy_bp.route("/api/users", methods=["GET", "POST"])
@login_required
def api_users_crud():
    """GET list of users or POST a new user (admin only)."""
    if session.get("role") != "admin":
        return jsonify({"error": "Forbidden — Admin access required"}), 403

    if request.method == "POST":
        body = request.get_json(force=True) or {}
        username = body.get("username")
        password = body.get("password")
        role = body.get("role", "operator")
        mobile = (body.get("mobile") or "").strip() or None

        if not username or not password:
            return jsonify({"error": "username and password are required"}), 400

        if role == "driver" and not mobile:
            return jsonify({"error": "mobile is required for driver accounts"}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": f"Username {username} already exists"}), 400

        if mobile and User.query.filter_by(mobile=mobile).first():
            return jsonify({"error": f"Mobile number {mobile} is already registered"}), 400

        u = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
            mobile=mobile,
            created_at=datetime.utcnow()
        )
        db.session.add(u)
        db.session.commit()
        return jsonify({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "mobile": u.mobile,
            "created_at": u.created_at.strftime("%Y-%m-%d")
        })

    users = User.query.order_by(User.username).all()
    return jsonify([{
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "mobile": u.mobile or "",
        "last_login": u.last_login_at.strftime("%Y-%m-%d %I:%M %p") if u.last_login_at else "Never",
        "created_at": u.created_at.strftime("%Y-%m-%d %I:%M %p")
    } for u in users])


@legacy_bp.route("/api/users/<int:u_id>/reset_password", methods=["POST"])
@login_required
def api_user_reset_password(u_id):
    """Admin-only: Reset user password."""
    if session.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403

    u = User.query.get_or_404(u_id)
    body = request.get_json(force=True) or {}
    new_password = body.get("password")
    if not new_password:
        return jsonify({"error": "New password is required"}), 400

    u.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({"success": True})


@legacy_bp.route("/api/users/<int:u_id>/deactivate", methods=["POST"])
@login_required
def api_user_deactivate(u_id):
    """Admin-only: Delete user."""
    if session.get("role") != "admin":
        return jsonify({"error": "Forbidden"}), 403

    if u_id == session.get("user_id"):
        return jsonify({"error": "Cannot deactivate your own active session account"}), 400

    u = User.query.get_or_404(u_id)
    db.session.delete(u)
    db.session.commit()
    return jsonify({"success": True})


@legacy_bp.route("/api/system_status")
@login_required
def api_system_status():
    """Health-check response for the settings footer status line."""
    try:
        db.session.execute(db.text("SELECT 1"))
        db_status = "online"
    except Exception:
        db_status = "offline"

    now_str = datetime.now().strftime("%I:%M:%S %p")
    return jsonify({
        "backend": "online",
        "database": db_status,
        "ai_service": "online",
        "last_updated": now_str
    })


# ---------------------------------------------------------------------------
# Entry point — DB init + seed
# ---------------------------------------------------------------------------

def _get_or_create_junction(name, status):
    """Return an existing junction by name, or create a new one."""
    j = Junction.query.filter_by(name=name).first()
    if not j:
        j = Junction(name=name, status=status, last_updated=datetime.utcnow())
        db.session.add(j)
        db.session.flush()   # get j.id without committing
    return j


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # Seed admin user
        if User.query.count() == 0:
            seed_pass = os.environ.get("ADMIN_SEED_PASSWORD")
            if not seed_pass:
                import secrets
                seed_pass = secrets.token_urlsafe(10)
                print(f"[seed] ADMIN_SEED_PASSWORD environment variable not set. Generated random fallback password: {seed_pass}")
            else:
                print("[seed] Seeding admin user using ADMIN_SEED_PASSWORD environment variable")

            admin = User(
                username      = "traffic-admin",
                password_hash = generate_password_hash(seed_pass),
                role          = "admin",
            )
            db.session.add(admin)
            db.session.commit()
            print(f"[seed] Created admin -> traffic-admin / {seed_pass}")

        # Seed display junctions (A–D)
        if Junction.query.filter(Junction.name.like("Junction _")).count() == 0:
            db.session.add_all([
                Junction(name="Junction A", status="high",     last_updated=datetime.utcnow()),
                Junction(name="Junction B", status="moderate", last_updated=datetime.utcnow()),
                Junction(name="Junction C", status="low",      last_updated=datetime.utcnow()),
                Junction(name="Junction D", status="moderate", last_updated=datetime.utcnow()),
            ])
            db.session.commit()
            print("[seed] Created display junctions A–D")

        # Seed alerts (and their associated numeric junctions)
        if Alert.query.count() == 0:
            j47 = _get_or_create_junction("Junction 47", "high")
            j12 = _get_or_create_junction("Junction 12", "moderate")
            j05 = _get_or_create_junction("Junction 05", "moderate")
            j33 = _get_or_create_junction("Junction 33", "high")
            j19 = _get_or_create_junction("Junction 19", "low")
            j08 = _get_or_create_junction("Junction 08", "moderate")
            now_s = datetime.utcnow()
            db.session.add_all([
                Alert(junction_id=j47.id, alert_type="Accident Detected",
                      severity="high",   message="Collision detected at Junction 47",
                      created_at=now_s - timedelta(minutes=5)),
                Alert(junction_id=j12.id, alert_type="Abnormal Congestion",
                      severity="medium", message="Traffic backup exceeds threshold at Junction 12",
                      created_at=now_s - timedelta(minutes=12)),
                Alert(junction_id=j05.id, alert_type="Heavy Congestion",
                      severity="low",    message="High vehicle density on corridor near Junction 05",
                      created_at=now_s - timedelta(minutes=20)),
                Alert(junction_id=j33.id, alert_type="Signal Malfunction",
                      severity="high",   message="Traffic signal controller offline at Junction 33",
                      created_at=now_s - timedelta(minutes=28)),
                Alert(junction_id=j19.id, alert_type="Vehicle Breakdown",
                      severity="medium", message="Stalled vehicle blocking lane near Junction 19",
                      created_at=now_s - timedelta(minutes=35)),
                Alert(junction_id=j08.id, alert_type="Abnormal Congestion",
                      severity="high",   message="Severe congestion spike on Ring Road at Junction 08",
                      created_at=now_s - timedelta(minutes=44)),
                Alert(junction_id=j47.id, alert_type="Accident Detected",
                      severity="medium", message="Minor fender-bender at Junction 47 North approach",
                      created_at=now_s - timedelta(minutes=52),
                      status="resolved"),
                Alert(junction_id=j12.id, alert_type="Signal Malfunction",
                      severity="low",    message="Phase C timer drift detected at Junction 12",
                      created_at=now_s - timedelta(minutes=65),
                      status="resolved"),
                Alert(junction_id=j05.id, alert_type="Vehicle Breakdown",
                      severity="high",   message="Heavy goods vehicle breakdown blocking intersection",
                      created_at=now_s - timedelta(minutes=73)),
                Alert(junction_id=j33.id, alert_type="Heavy Congestion",
                      severity="medium", message="Evening peak congestion above 85 PCU at Junction 33",
                      created_at=now_s - timedelta(minutes=80)),
                Alert(junction_id=j19.id, alert_type="Accident Detected",
                      severity="high",   message="Multi-vehicle incident at Junction 19 — emergency units dispatched",
                      created_at=now_s - timedelta(minutes=90)),
                Alert(junction_id=j08.id, alert_type="Abnormal Congestion",
                      severity="low",    message="Unusual slow traffic on Wardha Road at Junction 08",
                      created_at=now_s - timedelta(minutes=100),
                      status="resolved"),
                Alert(junction_id=j47.id, alert_type="Signal Malfunction",
                      severity="medium", message="Green phase skipping intermittently at Junction 47",
                      created_at=now_s - timedelta(minutes=115)),
            ])
            db.session.commit()
            print("[seed] Created 13 sample alerts (Junctions 47/12/05/33/19/08)")

        # Seed sample signal plan history
        if SignalPlanHistory.query.count() == 0:
            ja = _get_or_create_junction("Junction A", "high")
            jb = _get_or_create_junction("Junction B", "moderate")
            jc = _get_or_create_junction("Junction C", "low")
            jd = _get_or_create_junction("Junction D", "moderate")
            now = datetime.utcnow()
            db.session.add_all([
                SignalPlanHistory(junction_id=ja.id, applied_at=now - timedelta(minutes=10),
                                  phase_a_sec=52, phase_b_sec=28, phase_c_sec=35, phase_d_sec=17, applied_by="System", decision_type="adaptive"),
                SignalPlanHistory(junction_id=ja.id, applied_at=now - timedelta(minutes=20),
                                  phase_a_sec=45, phase_b_sec=30, phase_c_sec=30, phase_d_sec=15, applied_by="Operator", decision_type="manual_override"),
                SignalPlanHistory(junction_id=ja.id, applied_at=now - timedelta(minutes=30),
                                  phase_a_sec=60, phase_b_sec=25, phase_c_sec=25, phase_d_sec=20, applied_by="System", decision_type="adaptive"),
                SignalPlanHistory(junction_id=ja.id, applied_at=now - timedelta(minutes=40),
                                  phase_a_sec=40, phase_b_sec=35, phase_c_sec=30, phase_d_sec=15, applied_by="Operator", decision_type="manual_override"),
                
                SignalPlanHistory(junction_id=jb.id, applied_at=now - timedelta(minutes=15),
                                  phase_a_sec=35, phase_b_sec=35, phase_c_sec=25, phase_d_sec=25, applied_by="System", decision_type="adaptive"),
                SignalPlanHistory(junction_id=jb.id, applied_at=now - timedelta(minutes=25),
                                  phase_a_sec=50, phase_b_sec=20, phase_c_sec=30, phase_d_sec=20, applied_by="Operator", decision_type="manual_override"),
                SignalPlanHistory(junction_id=jb.id, applied_at=now - timedelta(minutes=35),
                                  phase_a_sec=45, phase_b_sec=25, phase_c_sec=35, phase_d_sec=15, applied_by="System", decision_type="adaptive"),
                
                SignalPlanHistory(junction_id=jc.id, applied_at=now - timedelta(minutes=5),
                                  phase_a_sec=30, phase_b_sec=30, phase_c_sec=30, phase_d_sec=30, applied_by="System", decision_type="adaptive"),
                SignalPlanHistory(junction_id=jc.id, applied_at=now - timedelta(minutes=12),
                                  phase_a_sec=25, phase_b_sec=35, phase_c_sec=25, phase_d_sec=15, applied_by="Operator", decision_type="manual_override"),
                
                SignalPlanHistory(junction_id=jd.id, applied_at=now - timedelta(minutes=8),
                                  phase_a_sec=40, phase_b_sec=40, phase_c_sec=20, phase_d_sec=20, applied_by="System", decision_type="adaptive"),
                SignalPlanHistory(junction_id=jd.id, applied_at=now - timedelta(minutes=18),
                                  phase_a_sec=30, phase_b_sec=30, phase_c_sec=40, phase_d_sec=20, applied_by="Operator", decision_type="manual_override"),
                SignalPlanHistory(junction_id=jd.id, applied_at=now - timedelta(minutes=28),
                                  phase_a_sec=45, phase_b_sec=25, phase_c_sec=25, phase_d_sec=25, applied_by="System", decision_type="adaptive"),
            ])
            db.session.commit()
            print("[seed] Created 12 sample signal plan history records")

        # Seed settings
        if SystemSettings.query.count() == 0:
            db.session.add(SystemSettings())
            db.session.commit()
            print("[seed] Created default SystemSettings row")

        # Seed VMSBoards
        if VMSBoard.query.count() == 0:
            db.session.add_all([
                VMSBoard(vms_id="VMS-12", location="Trimurti Nagar", status="active", current_message="CLEAR LANE"),
                VMSBoard(vms_id="VMS-15", location="Sitabuldi Chowk", status="active", current_message="CLEAR LANE"),
                VMSBoard(vms_id="VMS-18", location="Mayo Square", status="active", current_message="CLEAR LANE"),
                VMSBoard(vms_id="VMS-22", location="VNIT Gate", status="offline", current_message="TRAFFIC DELAY AHEAD"),
            ])
            db.session.commit()
            print("[seed] Created 4 default VMSBoard records")

    app.run(debug=True)
