import re

with open('app.py', 'r') as f:
    content = f.read()

auth_marker = "# ---------------------------------------------------------------------------\n# Auth helper"
routes_start = content.find(auth_marker)

if routes_start != -1:
    routes_part = content[routes_start:]
    
    legacy = """from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, send_file
import os, io, math, random, time
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models import *
from app.routes.dashboard import login_required
from app.config import Config

legacy_bp = Blueprint('legacy', __name__)
BASE_DIR = Config.BASE_DIR

"""
    # Replace @app.route with @legacy_bp.route
    routes_only = re.sub(r'@app\.route', '@legacy_bp.route', routes_part)
    
    # We will remove the login_required decorator definition since it's now imported,
    # and the auth/login/logout routes, and the dashboard route from the legacy_bp to avoid conflict.
    
    # Actually, simpler to just rename the auth/dashboard functions in legacy or drop them.
    # Let's remove them using regex or just keep them and don't register auth_bp and dashboard_bp yet.
    # The plan says to extract all. Let's just create legacy_bp for now to test the structure.
    
    with open('app/routes/legacy_routes.py', 'w') as out:
        out.write(legacy)
        out.write(routes_only)
