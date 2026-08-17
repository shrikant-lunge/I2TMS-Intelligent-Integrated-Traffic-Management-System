from flask import Blueprint, render_template
from functools import wraps
from flask import session, redirect, url_for

dashboard_bp = Blueprint('dashboard', __name__)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
@login_required
def dashboard_view():
    return render_template("dashboard.html", active_page="dashboard", page_name="Dashboard")
