"""
EmergencyCorridorEvent
----------------------
One row per significant event that occurs during an active corridor.

EVENT_TYPE values:
  CORRIDOR_STARTED
  JUNCTION_APPROACHED
  SIGNAL_PRIORITY_ACTIVATED
  JUNCTION_PASSED
  VMS_WARNING_ACTIVATED
  VMS_PASSED
  ANPR_TRIGGERED
  HOSPITAL_REACHED
  CORRIDOR_COMPLETED
  CORRIDOR_CLOSED

Written by:  EmergencyCorridorService simulation loop
Read by:     /emergency-corridor/<id>  (event timeline)
             /report  (emergency events section)
"""

from datetime import datetime
from app.extensions import db


class EmergencyCorridorEvent(db.Model):
    __tablename__ = "emergency_corridor_events"

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    corridor_id  = db.Column(db.String(20), db.ForeignKey("emergency_corridors.corridor_id"),
                             nullable=False, index=True)

    event_type   = db.Column(db.String(50), nullable=False, index=True)
    junction_id  = db.Column(db.Integer, db.ForeignKey("junctions.id"), nullable=True)
    vms_id       = db.Column(db.String(50), nullable=True)
    latitude     = db.Column(db.Float, nullable=True)
    longitude    = db.Column(db.Float, nullable=True)
    description  = db.Column(db.String(500), nullable=True)
    event_data   = db.Column(db.JSON, nullable=True)
    # Stores arbitrary structured payload, e.g. signal states, VMS message, etc.

    created_at   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    corridor = db.relationship("EmergencyCorridorRecord", back_populates="events")
    junction = db.relationship("Junction", backref=db.backref("corridor_events", lazy="dynamic"))

    def __repr__(self):
        return f"<EmergencyCorridorEvent [{self.event_type}] corridor={self.corridor_id} @ {self.created_at}>"
