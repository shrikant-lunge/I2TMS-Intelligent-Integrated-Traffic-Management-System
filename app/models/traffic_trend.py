"""
TrafficTrend
------------
Pre-aggregated traffic counts bucketed by time interval.

Written by:  AdaptiveSignalPipeline (after each process call) or a background
             aggregator that groups TrafficStateSnapshot rows.
Read by:     /api/dashboard_summary  (traffic trend chart)
             /report  (congestion trends section)
"""

from datetime import datetime
from app.extensions import db


class TrafficTrend(db.Model):
    __tablename__ = "traffic_trends"

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    junction_id      = db.Column(db.Integer, db.ForeignKey("junctions.id"), nullable=True, index=True)
    junction_name    = db.Column(db.String(120), nullable=True, index=True)

    # Time bucket (rounded to nearest 5-minute interval)
    time_bucket      = db.Column(db.DateTime, nullable=False, index=True)

    # Aggregated values for this bucket
    vehicle_count    = db.Column(db.Integer, nullable=False, default=0)
    pcu              = db.Column(db.Float,   nullable=False, default=0.0)
    congestion_level = db.Column(db.String(10), nullable=False, default="LOW")
    # "HIGH" | "MEDIUM" | "LOW"
    average_speed    = db.Column(db.Float,   nullable=True)
    traffic_level    = db.Column(db.String(10), nullable=True)

    created_at       = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    junction = db.relationship("Junction", backref=db.backref("traffic_trends", lazy="dynamic"))

    def __repr__(self):
        return (f"<TrafficTrend {self.junction_name or 'ALL'} "
                f"bucket={self.time_bucket} level={self.congestion_level}>")
