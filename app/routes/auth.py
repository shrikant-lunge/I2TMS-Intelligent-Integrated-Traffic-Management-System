from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash
from app.models.user import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            
            # Update last login
            from datetime import datetime
            from app.extensions import db
            user.last_login_at = datetime.utcnow()
            db.session.commit()
            
            return redirect(url_for("dashboard.dashboard_view"))
        else:
            return render_template("login.html", error="Invalid credentials")
            
    return render_template("login.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
