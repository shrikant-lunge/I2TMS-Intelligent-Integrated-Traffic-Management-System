from datetime import datetime
from app.extensions import db

class Alert(db.Model):
    __tablename__ = "alerts"

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    junction_id = db.Column(db.Integer, db.ForeignKey("junctions.id"), nullable=True)
    alert_type  = db.Column(db.String(100), nullable=False)
    severity    = db.Column(db.String(20), nullable=False, default="low")  # 'high' | 'medium' | 'low'
    message     = db.Column(db.String(500), nullable=True)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status      = db.Column(db.String(20), nullable=False, default="active")  # 'active' | 'resolved'

    def __repr__(self):
        return f"<Alert {self.alert_type} [{self.severity}]>"
