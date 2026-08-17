from datetime import datetime
from app.extensions import db

class SignalPlanHistory(db.Model):
    __tablename__ = "signal_plan_history"

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    junction_id   = db.Column(db.Integer, db.ForeignKey("junctions.id"), nullable=False)
    applied_at    = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    phase_a_sec   = db.Column(db.Integer, nullable=False, default=30)
    phase_b_sec   = db.Column(db.Integer, nullable=False, default=30)
    phase_c_sec   = db.Column(db.Integer, nullable=False, default=30)
    phase_d_sec   = db.Column(db.Integer, nullable=False, default=30)
    applied_by    = db.Column(db.String(20), nullable=False, default="System")  # 'System' | 'Operator'
    decision_type = db.Column(db.String(20), nullable=False, default="adaptive")  # 'adaptive' | 'manual_override'

    # Relationship
    junction = db.relationship("Junction", backref=db.backref("signal_history", lazy=True))

    def __repr__(self):
        return f"<SignalPlanHistory J{self.junction_id} @ {self.applied_at} by {self.applied_by} type {self.decision_type}>"
