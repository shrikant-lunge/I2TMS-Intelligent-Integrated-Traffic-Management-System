from app.extensions import db

class SystemSettings(db.Model):
    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    time_zone = db.Column(db.String(100), default="Asia/Kolkata")
    data_refresh_interval_sec = db.Column(db.Integer, default=10)
    default_dashboard_view = db.Column(db.String(100), default="overview")
    units = db.Column(db.String(20), default="metric")
    email_alerts = db.Column(db.Boolean, default=True)
    sms_alerts = db.Column(db.Boolean, default=True)
    push_notifications = db.Column(db.Boolean, default=True)
    emergency_alerts = db.Column(db.Boolean, default=True)
    default_cycle_time_sec = db.Column(db.Integer, default=90)
    min_phase_duration_sec = db.Column(db.Integer, default=10)
    max_phase_duration_sec = db.Column(db.Integer, default=60)

    def __repr__(self):
        return f"<SystemSettings id={self.id} tz={self.time_zone}>"
