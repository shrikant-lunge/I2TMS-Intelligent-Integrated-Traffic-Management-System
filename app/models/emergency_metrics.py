"""
EmergencyMetrics
----------------
Final measurable outcomes for a completed emergency corridor.

Calculated from EmergencyCorridorRecord + its events/ANPR when the
corridor reaches COMPLETED or CLOSED status.

Written by:  EmergencyCorridorService._finish_corridor()
Read by:     /emergency-corridor/<id>  (right-side metric panel)
             /report  (emergency response metrics section)
"""

from datetime import datetime
from app.extensions import db


class EmergencyMetrics(db.Model):
    __tablename__ = "emergency_metrics"

    id                          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    corridor_id                 = db.Column(db.String(20),
                                            db.ForeignKey("emergency_corridors.corridor_id"),
                                            nullable=False, unique=True, index=True)

    # Journey times
    departure_time              = db.Column(db.DateTime, nullable=True)
    arrival_time                = db.Column(db.DateTime, nullable=True)
    baseline_eta_minutes        = db.Column(db.Float, nullable=True)
    actual_or_simulated_eta_minutes = db.Column(db.Float, nullable=True)
    time_saved_minutes          = db.Column(db.Float, nullable=True)

    # Crossings
    junctions_crossed           = db.Column(db.Integer, nullable=False, default=0)
    signals_prioritized         = db.Column(db.Integer, nullable=False, default=0)
    vms_activated               = db.Column(db.Integer, nullable=False, default=0)
    anpr_detections             = db.Column(db.Integer, nullable=False, default=0)

    # Delay / event totals
    total_signal_delay          = db.Column(db.Float, nullable=True)  # seconds
    total_vms_events            = db.Column(db.Integer, nullable=False, default=0)

    created_at                  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    corridor = db.relationship("EmergencyCorridorRecord", back_populates="metrics")

    def __repr__(self):
        return (f"<EmergencyMetrics corridor={self.corridor_id} "
                f"saved={self.time_saved_minutes}min junctions={self.junctions_crossed}>")
