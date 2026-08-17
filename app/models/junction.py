from datetime import datetime
from app.extensions import db

class Junction(db.Model):
    __tablename__ = "junctions"

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name                 = db.Column(db.String(100), nullable=False)
    lat                  = db.Column(db.Float, nullable=True)
    lng                  = db.Column(db.Float, nullable=True)
    status               = db.Column(db.String(20), nullable=False, default="low")  # 'high' | 'moderate' | 'low'
    camera_thumbnail_url = db.Column(db.String(512), nullable=True)
    last_updated         = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    alerts = db.relationship("Alert", backref="junction", lazy=True)

    def __repr__(self):
        return f"<Junction {self.name} ({self.status})>"
