from app import create_app
from app.extensions import db
from app.models import *
import os, io
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

app = create_app()

def _get_or_create_junction(name, status):
    j = Junction.query.filter_by(name=name).first()
    if not j:
        j = Junction(name=name, status=status)
        db.session.add(j)
        db.session.commit()
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
                Junction(name="Junction A", status="high",     lat=21.1440, lng=79.0835, last_updated=datetime.utcnow()),
                Junction(name="Junction B", status="moderate", lat=21.1400, lng=79.0750, last_updated=datetime.utcnow()),
                Junction(name="Junction C", status="low",      lat=21.1350, lng=79.0650, last_updated=datetime.utcnow()),
                Junction(name="Junction D", status="moderate", lat=21.1310, lng=79.0570, last_updated=datetime.utcnow()),
                Junction(name="Rahate Colony Square", status="moderate", lat=21.1458, lng=79.0788, last_updated=datetime.utcnow()),
                Junction(name="VNIT Gate", status="high", lat=21.1253, lng=79.0514, last_updated=datetime.utcnow()),
                Junction(name="Ambazari T-Point", status="moderate", lat=21.1310, lng=79.0530, last_updated=datetime.utcnow()),
                Junction(name="Law College Square", status="high", lat=21.1367, lng=79.0620, last_updated=datetime.utcnow()),
                Junction(name="Shankar Nagar Sq", status="low", lat=21.1390, lng=79.0680, last_updated=datetime.utcnow()),
                Junction(name="Variety Square", status="high", lat=21.1482, lng=79.0742, last_updated=datetime.utcnow()),
                Junction(name="Medical Square", status="high", lat=21.1453, lng=79.0815, last_updated=datetime.utcnow()),
                Junction(name="Sitabuldi Junction", status="high", lat=21.1458, lng=79.0788, last_updated=datetime.utcnow()),
                Junction(name="Zero Mile", status="moderate", lat=21.1467, lng=79.0861, last_updated=datetime.utcnow())
            ])
            db.session.commit()
            print("[seed] Created real and display junctions")

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
                VMSBoard(vms_id="VMS-12", location="Trimurti Nagar", lat=21.1340, lng=79.0575, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-15", location="Sitabuldi Chowk", lat=21.1458, lng=79.0788, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-18", location="Mayo Square", lat=21.1497, lng=79.0856, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-01", location="VNIT Road", lat=21.1280, lng=79.0522, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-02", location="Ambazari Road", lat=21.1340, lng=79.0575, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-03", location="Law College Road", lat=21.1378, lng=79.0650, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-04", location="Shankar Nagar Road", lat=21.1420, lng=79.0710, status="active", current_message="NORMAL TRAFFIC"),
                VMSBoard(vms_id="VMS-05", location="Medical Square Appr", lat=21.1445, lng=79.0800, status="active", current_message="NORMAL TRAFFIC")
            ])
            db.session.commit()
            print("[seed] Created default VMSBoard records")

    