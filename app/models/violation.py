from datetime import datetime
from app.extensions import db

class Violation(db.Model):
    __tablename__ = "violations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    emergency_request_id = db.Column(db.Integer, db.ForeignKey('emergency_requests.id'))
    violation_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    vehicle_tracking_id = db.Column(db.Integer, nullable=False)
    vehicle_type = db.Column(db.String(30), nullable=True)
    plate_number = db.Column(db.String(30), nullable=True)
    plate_confidence = db.Column(db.Float, nullable=True)
    detection_confidence = db.Column(db.Float, nullable=True)
    violation_type = db.Column(db.String(50), default="EMERGENCY_CORRIDOR_BLOCKING")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    evidence_path = db.Column(db.String(500), nullable=True)
    blocking_duration = db.Column(db.Float, nullable=True)  # seconds
    movement_status = db.Column(db.String(20), nullable=True)  # STOPPED, SLOW
    status = db.Column(db.String(30), default="DETECTED")
    # DETECTED, VERIFIED, NEEDS_REVIEW, CHALLAN_GENERATED, REJECTED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    emergency_request = db.relationship("EmergencyRequest", backref=db.backref("violations", lazy=True))
