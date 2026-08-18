"""
I²TMS — seed.py
===============
Seeds the database with:
  1. Admin user
  2. Real Nagpur junctions (with coordinates)
  3. Alert samples
  4. Signal plan history samples
  5. System settings + VMS boards
  6. ONE demo EmergencyCorridorRecord (COMPLETED) with events, ANPR detections,
     and EmergencyMetrics — so dashboard and corridor pages work on first launch.

Run:
    python seed.py
"""

from app import create_app
from app.extensions import db
from app.models import (
    User, Junction, Alert, SignalPlanHistory, VMSBoard, SystemSettings,
    EmergencyCorridorRecord, EmergencyCorridorEvent, ANPRDetection, EmergencyMetrics,
)
import os
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

app = create_app()


def _get_or_create_junction(name, status, lat=None, lng=None):
    j = Junction.query.filter_by(name=name).first()
    if not j:
        j = Junction(name=name, status=status, lat=lat, lng=lng,
                     last_updated=datetime.utcnow())
        db.session.add(j)
        db.session.flush()
    return j


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # ── 1. Admin user ────────────────────────────────────────────────
        if User.query.count() == 0:
            seed_pass = os.environ.get("ADMIN_SEED_PASSWORD", "Admin@1234")
            admin = User(
                username      = "traffic-admin",
                password_hash = generate_password_hash(seed_pass),
                role          = "admin",
                created_at    = datetime.utcnow(),
            )
            db.session.add(admin)
            db.session.commit()
            print(f"[seed] Created admin → traffic-admin / {seed_pass}")

        # ── 2. Real Nagpur junctions ─────────────────────────────────────
        NAGPUR_JUNCTIONS = [
            # (name, status, lat, lng)
            ("Rahate Colony Square",        "moderate", 21.1458, 79.0788),
            ("VNIT Gate",                   "high",     21.1253, 79.0514),
            ("Ambazari T-Point",            "moderate", 21.1310, 79.0530),
            ("Law College Square",          "high",     21.1367, 79.0620),
            ("Shankar Nagar Square",        "low",      21.1390, 79.0680),
            ("Variety Square",              "high",     21.1482, 79.0742),
            ("Medical Square",              "high",     21.1453, 79.0815),
            ("Sitabuldi Junction",          "high",     21.1458, 79.0788),
            ("Zero Mile",                   "moderate", 21.1467, 79.0861),
            ("Deekshabhoomi Square",        "moderate", 21.1308, 79.0468),
            ("Pratap Nagar Square",         "low",      21.1570, 79.0890),
            ("Bansi Nagar",           "moderate", 21.1400, 79.0720),
            # Legacy A–D kept for backward compat
            ("Junction A",                  "high",     21.1440, 79.0835),
            ("Junction B",                  "moderate", 21.1400, 79.0750),
            ("Junction C",                  "low",      21.1350, 79.0650),
            ("Junction D",                  "moderate", 21.1310, 79.0570),
        ]

        if Junction.query.filter(Junction.name.like("%Junction%")).count() == 0 and \
           Junction.query.filter(Junction.name.like("Rahate%")).count() == 0:
            for name, status, lat, lng in NAGPUR_JUNCTIONS:
                _get_or_create_junction(name, status, lat, lng)
            db.session.commit()
            print(f"[seed] Created {len(NAGPUR_JUNCTIONS)} Nagpur junctions")
        else:
            # Ensure at least the key junctions exist
            for name, status, lat, lng in NAGPUR_JUNCTIONS:
                _get_or_create_junction(name, status, lat, lng)
            db.session.commit()
            print("[seed] Junctions verified/updated")

        # ── 3. Sample alerts ──────────────────────────────────────────────
        if Alert.query.count() == 0:
            now_s = datetime.utcnow()
            j47 = _get_or_create_junction("Junction 47", "high",  21.1510, 79.0870)
            j12 = _get_or_create_junction("Junction 12", "moderate", 21.1420, 79.0780)
            j05 = _get_or_create_junction("Junction 05", "moderate", 21.1380, 79.0710)
            j33 = _get_or_create_junction("Junction 33", "high",  21.1490, 79.0840)
            j19 = _get_or_create_junction("Junction 19", "low",   21.1340, 79.0600)
            j08 = _get_or_create_junction("Junction 08", "moderate", 21.1410, 79.0760)
            db.session.add_all([
                Alert(junction_id=j47.id, alert_type="Accident Detected",    severity="high",   message="Collision detected at Junction 47",                              created_at=now_s - timedelta(minutes=5)),
                Alert(junction_id=j12.id, alert_type="Abnormal Congestion",  severity="medium", message="Traffic backup exceeds threshold at Junction 12",               created_at=now_s - timedelta(minutes=12)),
                Alert(junction_id=j05.id, alert_type="Heavy Congestion",     severity="low",    message="High vehicle density on corridor near Junction 05",             created_at=now_s - timedelta(minutes=20)),
                Alert(junction_id=j33.id, alert_type="Signal Malfunction",   severity="high",   message="Traffic signal controller offline at Junction 33",              created_at=now_s - timedelta(minutes=28)),
                Alert(junction_id=j19.id, alert_type="Vehicle Breakdown",    severity="medium", message="Stalled vehicle blocking lane near Junction 19",               created_at=now_s - timedelta(minutes=35)),
                Alert(junction_id=j08.id, alert_type="Abnormal Congestion",  severity="high",   message="Severe congestion spike on Ring Road at Junction 08",          created_at=now_s - timedelta(minutes=44)),
                Alert(junction_id=j47.id, alert_type="Signal Malfunction",   severity="medium", message="Green phase skipping intermittently at Junction 47",           created_at=now_s - timedelta(minutes=115)),
            ])
            db.session.commit()
            print("[seed] Created sample alerts")

        # ── 4. Signal plan history ─────────────────────────────────────────
        if SignalPlanHistory.query.count() == 0:
            ja = _get_or_create_junction("Junction A", "high")
            jb = _get_or_create_junction("Junction B", "moderate")
            jc = _get_or_create_junction("Junction C", "low")
            jd = _get_or_create_junction("Junction D", "moderate")
            now = datetime.utcnow()
            db.session.add_all([
                SignalPlanHistory(junction_id=ja.id, applied_at=now - timedelta(minutes=10), phase_a_sec=52, phase_b_sec=28, phase_c_sec=35, phase_d_sec=17, applied_by="System",   decision_type="adaptive"),
                SignalPlanHistory(junction_id=ja.id, applied_at=now - timedelta(minutes=20), phase_a_sec=45, phase_b_sec=30, phase_c_sec=30, phase_d_sec=15, applied_by="Operator", decision_type="manual_override"),
                SignalPlanHistory(junction_id=jb.id, applied_at=now - timedelta(minutes=15), phase_a_sec=35, phase_b_sec=35, phase_c_sec=25, phase_d_sec=25, applied_by="System",   decision_type="adaptive"),
                SignalPlanHistory(junction_id=jc.id, applied_at=now - timedelta(minutes=5),  phase_a_sec=30, phase_b_sec=30, phase_c_sec=30, phase_d_sec=30, applied_by="System",   decision_type="adaptive"),
                SignalPlanHistory(junction_id=jd.id, applied_at=now - timedelta(minutes=8),  phase_a_sec=40, phase_b_sec=40, phase_c_sec=20, phase_d_sec=20, applied_by="System",   decision_type="adaptive"),
            ])
            db.session.commit()
            print("[seed] Created signal plan history")

        # ── 5. System settings + VMS boards ───────────────────────────────
        if SystemSettings.query.count() == 0:
            db.session.add(SystemSettings())
            db.session.commit()
            print("[seed] Created default SystemSettings")

        if VMSBoard.query.count() == 0:
            db.session.add_all([
                VMSBoard(vms_id="VMS-01", location="VNIT Road",             lat=21.1280, lng=79.0522, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-02", location="Ambazari Road",         lat=21.1340, lng=79.0575, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-03", location="Law College Road",      lat=21.1378, lng=79.0650, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-04", location="Shankar Nagar Road",    lat=21.1420, lng=79.0710, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-05", location="Medical Square Appr.",  lat=21.1445, lng=79.0800, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-12", location="Trimurti Nagar",        lat=21.1340, lng=79.0575, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-15", location="Sitabuldi Chowk",       lat=21.1458, lng=79.0788, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-18", location="Mayo Square",           lat=21.1497, lng=79.0856, status="active", current_message="NORMAL TRAFFIC"),
            ])
            db.session.commit()
            print("[seed] Created VMS boards")

        # ── 6. Demo EmergencyCorridorRecord ────────────────────────────────
        #
        # Creates one realistic COMPLETED corridor (VNIT → AIIMS Nagpur)
        # using actual data from routes.json / anpr_detections.json.
        # This makes the dashboard "Recent Emergency Corridors" and the
        # /emergency-corridor list non-empty on first launch.
        #
        DEMO_CORRIDOR_ID = "DEMO0001"

        if EmergencyCorridorRecord.query.filter_by(corridor_id=DEMO_CORRIDOR_ID).first() is None:
            # Timestamps: corridor ran about 2 hours ago
            now = datetime.utcnow()
            started    = now - timedelta(hours=2, minutes=18)
            completed  = started + timedelta(minutes=16)

            corridor = EmergencyCorridorRecord(
                corridor_id           = DEMO_CORRIDOR_ID,
                source_name           = "VNIT Nagpur",
                source_lat            = 21.123028,
                source_lon            = 79.051449,
                destination_name      = "AIIMS Nagpur",
                destination_lat       = 21.036856,
                destination_lon       = 79.027517,
                route_id              = "vnit_to_aiims",
                distance_km           = 15.3,
                baseline_eta_minutes  = 30.0,
                optimized_eta_minutes = 15.0,
                time_saved_minutes    = 15.0,
                status                = "COMPLETED",
                started_at            = started,
                completed_at          = completed,
                created_at            = started,
            )
            db.session.add(corridor)
            db.session.flush()

            # Events
            events = [
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="CORRIDOR_STARTED",
                    latitude=21.123028, longitude=79.051449,
                    description="Emergency corridor started: VNIT Nagpur → AIIMS Nagpur",
                    event_data={"distance_km": 15.3, "baseline_eta_minutes": 30.0, "optimized_eta_minutes": 15.0},
                    created_at=started),
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="SIGNAL_PRIORITY_ACTIVATED",
                    latitude=21.1253, longitude=79.0514,
                    description="Signal priority activated at Ambazari T-Point",
                    event_data={"junction": "Ambazari T-Point"},
                    created_at=started + timedelta(minutes=2)),
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="JUNCTION_PASSED",
                    latitude=21.1253, longitude=79.0514,
                    description="Ambulance passed junction Ambazari T-Point",
                    created_at=started + timedelta(minutes=3)),
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="VMS_WARNING_ACTIVATED",
                    vms_id="VMS-01",
                    latitude=21.1280, longitude=79.0522,
                    description="VMS 'VNIT Road' set to CLEAR LANE warning",
                    event_data={"message": "CLEAR THE RIGHT LANE\nEMERGENCY VEHICLE APPROACHING"},
                    created_at=started + timedelta(minutes=4)),
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="ANPR_TRIGGERED",
                    latitude=21.1253, longitude=79.0514,
                    description="ANPR demo triggered after junction Ambazari T-Point",
                    created_at=started + timedelta(minutes=4)),
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="SIGNAL_PRIORITY_ACTIVATED",
                    latitude=21.1310, longitude=79.0530,
                    description="Signal priority activated at Law College Square",
                    event_data={"junction": "Law College Square"},
                    created_at=started + timedelta(minutes=7)),
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="JUNCTION_PASSED",
                    latitude=21.1310, longitude=79.0530,
                    description="Ambulance passed junction Law College Square",
                    created_at=started + timedelta(minutes=8)),
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="VMS_PASSED",
                    vms_id="VMS-01",
                    description="Ambulance passed VMS 'VNIT Road'",
                    created_at=started + timedelta(minutes=9)),
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="SIGNAL_PRIORITY_ACTIVATED",
                    latitude=21.0800, longitude=79.0550,
                    description="Signal priority activated at Checkpoint 3",
                    event_data={"junction": "Checkpoint 3"},
                    created_at=started + timedelta(minutes=11)),
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="JUNCTION_PASSED",
                    latitude=21.0800, longitude=79.0550,
                    description="Ambulance passed junction Checkpoint 3",
                    created_at=started + timedelta(minutes=12)),
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="HOSPITAL_REACHED",
                    latitude=21.036856, longitude=79.027517,
                    description="Ambulance reached AIIMS Nagpur",
                    event_data={"destination": "AIIMS Nagpur"},
                    created_at=completed),
                EmergencyCorridorEvent(corridor_id=DEMO_CORRIDOR_ID, event_type="CORRIDOR_COMPLETED",
                    description="Emergency corridor completed successfully",
                    created_at=completed),
            ]
            db.session.add_all(events)

            # ANPR detections (from anpr_detections.json data)
            ANPR_DEMO = [
                # (plate, conf, is_primary, car_id, ts_sec, lat, lon)
                ("KA02HN1828", 0.538, True,  6,  7.30, 21.1253, 79.0514),
                ("KA02XH1826", 0.352, False, 6,  7.47, 21.1253, 79.0514),
                ("KA02KN1826", 0.494, False, 6,  7.80, 21.1253, 79.0514),
                ("KA02NN1828", 0.194, False, 6,  8.67, 21.1253, 79.0514),
                ("KA02MM9091", 0.958, True,  69, 20.97, 21.1310, 79.0530),
                ("KA02HH9091", 0.429, False, 69, 17.83, 21.1310, 79.0530),
                ("XA02HM9091", 0.315, False, 69, 17.80, 21.1310, 79.0530),
            ]

            anpr_detections_seed = []
            for plate, conf, is_primary, car_id, ts_sec, lat, lon in ANPR_DEMO:
                anpr_detections_seed.append(ANPRDetection(
                    corridor_id         = DEMO_CORRIDOR_ID,
                    plate_number        = plate,
                    confidence          = conf,
                    is_primary          = is_primary,
                    car_id              = car_id,
                    latitude            = lat,
                    longitude           = lon,
                    checkpoint_name     = "Ambulance CCTV",
                    detected_at         = started + timedelta(minutes=4) + timedelta(seconds=ts_sec),
                    video_timestamp_sec = ts_sec,
                    source              = "Ambulance CCTV",
                ))
            db.session.add_all(anpr_detections_seed)

            # Metrics
            db.session.add(EmergencyMetrics(
                corridor_id                     = DEMO_CORRIDOR_ID,
                departure_time                  = started,
                arrival_time                    = completed,
                baseline_eta_minutes            = 30.0,
                actual_or_simulated_eta_minutes = 16.0,
                time_saved_minutes              = 14.0,
                junctions_crossed               = 3,
                signals_prioritized             = 3,
                vms_activated                   = 2,
                anpr_detections                 = len(ANPR_DEMO),
                total_signal_delay              = 0.0,
                total_vms_events                = 2,
                created_at                      = completed,
            ))

            db.session.commit()
            print(f"[seed] Created demo corridor {DEMO_CORRIDOR_ID} with "
                  f"{len(events)} events and {len(ANPR_DEMO)} ANPR detections")
        else:
            print(f"[seed] Demo corridor {DEMO_CORRIDOR_ID} already exists — skipped")

        print("[seed] ✓ Database seed complete")
