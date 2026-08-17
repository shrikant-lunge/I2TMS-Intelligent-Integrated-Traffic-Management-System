from datetime import datetime
from app.extensions import db

class EmergencyRequest(db.Model):
    __tablename__ = "emergency_requests"

    id = db.Column(db.Integer, primary_key=True)
    vehicle_type = db.Column(db.String(50), nullable=False)          # 'ambulance' | 'fire_truck'
    vehicle_number = db.Column(db.String(50), nullable=False)
    current_location = db.Column(db.String(255), nullable=False)
    current_lat = db.Column(db.Float)
    current_lng = db.Column(db.Float)
    destination = db.Column(db.String(255), nullable=False)
    destination_lat = db.Column(db.Float)
    destination_lng = db.Column(db.Float)
    priority = db.Column(db.String(20), default='high')
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    status = db.Column(db.String(20), default='active')               # 'active' | 'completed' | 'cancelled'
    route_distance_km = db.Column(db.Float)
    route_eta_min = db.Column(db.Integer)
    route_data = db.Column(db.Text)   # JSON-serialized route geometry + checkpoints
    route_geometry = db.Column(db.Text)
    signals_on_route = db.Column(db.Integer)
    vms_on_route = db.Column(db.Integer)

    # Relationship for cleaner joins
    requester = db.relationship("User", foreign_keys=[requested_by])

    def __repr__(self):
        return f"<EmergencyRequest {self.id} vehicle={self.vehicle_number} status={self.status}>"
