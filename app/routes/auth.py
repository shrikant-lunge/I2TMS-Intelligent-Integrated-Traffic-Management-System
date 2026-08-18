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


# ---------------------------------------------------------------------------
# Driver (Ambulance) Authentication
# ---------------------------------------------------------------------------

@auth_bp.route("/driver-login", methods=["GET", "POST"])
def driver_login():
    """
    Standalone login page for ambulance drivers.
    Authenticates by mobile number + password (role must be 'driver').
    On success → /emergency/driver.
    """
    # Already authenticated as a driver? Go straight to the screen.
    if session.get("driver_id"):
        return redirect(url_for("emergency_corridor.driver_screen"))

    if request.method == "POST":
        mobile   = (request.form.get("mobile") or "").strip()
        password = request.form.get("password") or ""

        if not mobile or not password:
            return render_template("driver_login.html",
                                   error="Please enter your mobile number and password.")

        # Look up driver by mobile number; only allow role == 'driver'
        user = User.query.filter_by(mobile=mobile, role="driver").first()
        if user and check_password_hash(user.password_hash, password):
            session["driver_id"]       = user.id
            session["driver_mobile"]   = user.mobile
            session["driver_username"] = user.username

            # Update last login timestamp
            from datetime import datetime
            from app.extensions import db
            user.last_login_at = datetime.utcnow()
            db.session.commit()

            return redirect(url_for("emergency_corridor.driver_screen"))
        else:
            return render_template("driver_login.html",
                                   error="Invalid mobile number or password.")

    return render_template("driver_login.html")


@auth_bp.route("/driver-logout")
def driver_logout():
    """Log out the driver and return to driver login page."""
    session.pop("driver_id",       None)
    session.pop("driver_mobile",   None)
    session.pop("driver_username", None)
    return redirect(url_for("auth.driver_login"))

