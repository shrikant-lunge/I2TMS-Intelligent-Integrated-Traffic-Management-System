from datetime import datetime
from app.extensions import db

class User(db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(20), nullable=False, default="operator")  # 'admin' | 'operator'
    created_at    = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)
