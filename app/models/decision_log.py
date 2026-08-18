"""
DecisionLog
-----------
Human-readable audit log for every decision made by I²TMS.

Every SignalDecision automatically gets a companion DecisionLog row.
Manual overrides from the operator also produce a DecisionLog.

Written by:  AdaptiveSignalPipeline, legacy_routes (manual_override / apply_plan)
Read by:     /decision-logs  (paginated, filtered table)
             /report  (signal decisions section)
"""

from datetime import datetime
from app.extensions import db


class DecisionLog(db.Model):
    __tablename__ = "decision_logs"

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Source
    module              = db.Column(db.String(60), nullable=False, default="adaptive_signal")
    # "adaptive_signal" | "manual_override" | "emergency_corridor" | "system"

    # Location
    junction_id         = db.Column(db.Integer, db.ForeignKey("junctions.id"), nullable=True, index=True)
    junction_name       = db.Column(db.String(120), nullable=False, index=True)
    direction           = db.Column(db.String(10),  nullable=True)

    # Decision summary (human-readable)
    decision            = db.Column(db.String(100), nullable=False)
    # e.g. "EXTEND GREEN", "APPLY ADAPTIVE PLAN", "MANUAL OVERRIDE", "HOLD PHASE"
    reason              = db.Column(db.String(500), nullable=True)

    # Traffic state at decision time
    traffic_level       = db.Column(db.String(10), nullable=True)
    congestion_level    = db.Column(db.String(10), nullable=True)
    pcu                 = db.Column(db.Float, nullable=True)
    density             = db.Column(db.Float, nullable=True)
    green_time          = db.Column(db.Float, nullable=True)  # recommended/applied green time (seconds)

    # Optional link back to the signal_decisions row
    signal_decision_id  = db.Column(db.Integer, db.ForeignKey("signal_decisions.id"), nullable=True, index=True)

    # Extra payload (JSONB / TEXT)
    metadata_           = db.Column("metadata", db.JSON, nullable=True)
    # stores raw pipeline output or override details

    created_at          = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    junction        = db.relationship("Junction", backref=db.backref("decision_logs", lazy="dynamic"))
    signal_decision = db.relationship("SignalDecision", back_populates="log_entry", foreign_keys=[signal_decision_id])

    def __repr__(self):
        return (f"<DecisionLog [{self.module}] {self.junction_name}/{self.direction} "
                f"'{self.decision}' @ {self.created_at}>")
