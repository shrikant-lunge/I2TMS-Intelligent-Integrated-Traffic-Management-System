from flask import Blueprint, render_template, redirect, url_for

ambulance_bp = Blueprint('ambulance', __name__)


@ambulance_bp.route("/ambulance")
def driver_dashboard():
    """
    Legacy entry point — redirect to the new Emergency Driver screen.
    The old ambulance.html is preserved; this just forwards traffic so
    existing bookmarks keep working.
    """
    return redirect(url_for('emergency_corridor.driver_screen'))
