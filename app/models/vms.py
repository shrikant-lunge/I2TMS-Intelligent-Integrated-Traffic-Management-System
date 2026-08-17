from app.extensions import db

class VMSBoard(db.Model):
    __tablename__ = "vms_boards"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    vms_id = db.Column(db.String(50), unique=True, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default="active")   # 'active' | 'offline'
    current_message = db.Column(db.String(500), nullable=True)

    def __repr__(self):
        return f"<VMSBoard {self.vms_id} status={self.status}>"
