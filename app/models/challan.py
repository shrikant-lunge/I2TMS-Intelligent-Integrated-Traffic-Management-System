from datetime import datetime
from app.extensions import db

class Challan(db.Model):
    __tablename__ = "challans"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    violation_id = db.Column(db.Integer, db.ForeignKey('violations.id'))
    challan_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    vehicle_number = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(30), default='pending')  # pending | issued
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    violation = db.relationship("Violation", backref=db.backref("challan", uselist=False, lazy=True))
