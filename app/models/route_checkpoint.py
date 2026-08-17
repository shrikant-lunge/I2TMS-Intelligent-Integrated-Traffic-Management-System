from app.extensions import db

class RouteCheckpoint(db.Model):
    __tablename__ = "route_checkpoints"
    
    id = db.Column(db.Integer, primary_key=True)
    emergency_request_id = db.Column(db.Integer, db.ForeignKey('emergency_requests.id'))
    checkpoint_type = db.Column(db.String(20))  # 'junction' | 'vms'
    infrastructure_id = db.Column(db.Integer)    # junction.id or vms_board.id
    distance_along_route_m = db.Column(db.Float)
    order_index = db.Column(db.Integer)
    status = db.Column(db.String(20), default='pending')  # pending | active | passed
    activated_at = db.Column(db.DateTime, nullable=True)
    deactivated_at = db.Column(db.DateTime, nullable=True)
    
    # Relationship
    emergency_request = db.relationship("EmergencyRequest", backref=db.backref("checkpoints", lazy=True))
