"""
SignalDecision
--------------
One row per adaptive-signal calculation result.

Written by:  AdaptiveSignalPipeline._finalize_response()
Read by:     /decision-logs  (via DecisionLog foreign key)
             /report  (signal optimisation section)
"""

from datetime import datetime
from app.extensions import db


class SignalDecision(db.Model):
    __tablename__ = "signal_decisions"

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    junction_id          = db.Column(db.Integer, db.ForeignKey("junctions.id"), nullable=True, index=True)
    junction_name        = db.Column(db.String(120), nullable=False, index=True)
    direction            = db.Column(db.String(10),  nullable=False)

    # Inputs
    vehicle_count        = db.Column(db.Integer,  nullable=False, default=0)
    pcu                  = db.Column(db.Float,    nullable=False, default=0.0)
    density              = db.Column(db.Float,    nullable=False, default=0.0)
    congestion_level     = db.Column(db.String(10), nullable=False, default="LOW")
    traffic_level        = db.Column(db.String(10), nullable=False, default="LOW")

    # Webster output
    recommended_green_time = db.Column(db.Float, nullable=False, default=0.0)
    previous_green_time    = db.Column(db.Float, nullable=True)
    cycle_length_sec       = db.Column(db.Float, nullable=True)

    # Decision classification
    decision_type        = db.Column(db.String(30), nullable=False, default="adaptive")
    # "adaptive" | "manual_override" | "hold" | "extend_green" | "reduce_green"

    reason               = db.Column(db.String(500), nullable=True)
    source_kind          = db.Column(db.String(20), nullable=False, default="image")
    created_at           = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationship
    junction  = db.relationship("Junction", backref=db.backref("signal_decisions", lazy="dynamic"))
    log_entry = db.relationship("DecisionLog", back_populates="signal_decision",
                                uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return (f"<SignalDecision {self.junction_name}/{self.direction} "
                f"green={self.recommended_green_time}s @ {self.created_at}>")
