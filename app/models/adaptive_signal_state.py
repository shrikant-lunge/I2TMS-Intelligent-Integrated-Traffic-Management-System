from datetime import datetime

from app.extensions import db


class AdaptiveSignalState(db.Model):
    __tablename__ = "adaptive_signal_states"
    __table_args__ = (
        db.UniqueConstraint("junction_name", "direction", name="uq_adaptive_signal_state"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    junction_name = db.Column(db.String(120), nullable=False, index=True)
    direction = db.Column(db.String(10), nullable=False, index=True)
    vehicle_count_total = db.Column(db.Integer, nullable=False, default=0)
    vehicle_count_by_class = db.Column(db.JSON, nullable=False, default=dict)
    queue_length = db.Column(db.Integer, nullable=False, default=0)
    density = db.Column(db.Float, nullable=False, default=0.0)
    average_speed = db.Column(db.Float, nullable=False, default=0.0)
    occupancy = db.Column(db.Float, nullable=False, default=0.0)
    waiting_time = db.Column(db.Float, nullable=False, default=0.0)
    traffic_level = db.Column(db.String(20), nullable=False, default="LOW")
    pcu_demand = db.Column(db.Float, nullable=False, default=0.0)
    demand_rate_pcu_per_hr = db.Column(db.Float, nullable=False, default=0.0)
    congestion_level = db.Column(db.String(20), nullable=False, default="LOW")
    green_time_sec = db.Column(db.Float, nullable=False, default=0.0)
    source_kind = db.Column(db.String(20), nullable=False, default="image")
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<AdaptiveSignalState {self.junction_name} {self.direction} {self.traffic_level}>"