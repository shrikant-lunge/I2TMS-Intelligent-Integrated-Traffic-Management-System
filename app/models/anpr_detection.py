"""
ANPRDetection
-------------
One row per ANPR plate reading associated with an emergency corridor.

The source is the pre-recorded ANPR demo video + JSON timing data.
Detections are emitted progressively as the video plays, keyed to
anpr_detections.json timestamp_sec.

Written by:  EmergencyCorridorService._update_anpr()
Read by:     /emergency-corridor/<id>  (ANPR history panel)
             /api/emergency-corridor/<id>/export/anpr  (XLSX export)
             /report  (ANPR detections section)
"""

from datetime import datetime
from app.extensions import db


class ANPRDetection(db.Model):
    __tablename__ = "anpr_detections"

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    corridor_id     = db.Column(db.String(20), db.ForeignKey("emergency_corridors.corridor_id"),
                                nullable=False, index=True)

    plate_number    = db.Column(db.String(20), nullable=False)
    confidence      = db.Column(db.Float, nullable=True)
    is_primary      = db.Column(db.Boolean, nullable=False, default=False)
    car_id          = db.Column(db.Integer, nullable=True)
    # car_id from the ANPR JSON (unique vehicle tracked across frames)

    # Location of detection
    latitude        = db.Column(db.Float, nullable=True)
    longitude       = db.Column(db.Float, nullable=True)
    checkpoint_name = db.Column(db.String(200), nullable=True)

    # Timing
    detected_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    video_timestamp_sec = db.Column(db.Float, nullable=True)
    # Timestamp within the source video where this detection occurred

    # Source and evidence
    source          = db.Column(db.String(100), nullable=True, default="Ambulance CCTV")
    image_path      = db.Column(db.String(512), nullable=True)
    # Local path to a captured number-plate frame image (for future e-challan support)

    # Relationship
    corridor = db.relationship("EmergencyCorridorRecord", back_populates="anpr")

    def __repr__(self):
        return (f"<ANPRDetection plate={self.plate_number} conf={self.confidence} "
                f"corridor={self.corridor_id} @ {self.detected_at}>")
