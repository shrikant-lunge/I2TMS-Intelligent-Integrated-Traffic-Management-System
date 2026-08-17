from datetime import datetime
from app.extensions import db

class GeneratedReport(db.Model):
    __tablename__ = "generated_reports"

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    report_type  = db.Column(db.String(100), nullable=False)   # 'traffic_performance' | 'signal_optimization' | 'congestion' | 'emergency_response'
    time_range   = db.Column(db.String(50), nullable=False)    # 'today' | 'this_week' | 'this_month' | 'custom'
    range_start  = db.Column(db.DateTime, nullable=True)
    range_end    = db.Column(db.DateTime, nullable=True)
    generated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_path    = db.Column(db.String(512), nullable=True)

    # Relationship
    user = db.relationship("User", backref="reports", lazy=True)

    def __repr__(self):
        return f"<GeneratedReport {self.id} type={self.report_type} range={self.time_range}>"
