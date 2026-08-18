"""
TrafficStateSnapshot
--------------------
Persistent record of a traffic state produced by the adaptive-signal
pipeline for one junction / direction at a point in time.

Written by:  AdaptiveSignalPipeline._finalize_response()
Read by:     /api/dashboard_summary  (avg congestion, trend aggregation)
             /report  (traffic overview section)
"""

from datetime import datetime
from app.extensions import db


class TrafficStateSnapshot(db.Model):
    __tablename__ = "traffic_state_snapshots"

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    junction_id     = db.Column(db.Integer, db.ForeignKey("junctions.id"), nullable=True, index=True)
    junction_name   = db.Column(db.String(120), nullable=False, index=True)
    direction       = db.Column(db.String(10), nullable=False)

    # Vehicle counts
    vehicle_count   = db.Column(db.Integer,  nullable=False, default=0)
    car_count       = db.Column(db.Integer,  nullable=False, default=0)
    bus_count       = db.Column(db.Integer,  nullable=False, default=0)
    truck_count     = db.Column(db.Integer,  nullable=False, default=0)
    bike_count      = db.Column(db.Integer,  nullable=False, default=0)
    auto_count      = db.Column(db.Integer,  nullable=False, default=0)

    # Traffic metrics
    queue_length    = db.Column(db.Integer,  nullable=False, default=0)
    density         = db.Column(db.Float,    nullable=False, default=0.0)
    speed           = db.Column(db.Float,    nullable=False, default=0.0)
    occupancy       = db.Column(db.Float,    nullable=False, default=0.0)
    waiting_time    = db.Column(db.Float,    nullable=False, default=0.0)
    traffic_level   = db.Column(db.String(10), nullable=False, default="LOW")
    pcu_demand      = db.Column(db.Float,    nullable=False, default=0.0)
    congestion_level = db.Column(db.String(10), nullable=False, default="LOW")

    source_kind     = db.Column(db.String(20), nullable=False, default="image")  # "image" | "video"
    captured_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationship
    junction = db.relationship("Junction", backref=db.backref("traffic_snapshots", lazy="dynamic"))

    def __repr__(self):
        return f"<TrafficStateSnapshot {self.junction_name}/{self.direction} {self.traffic_level} @ {self.captured_at}>"
