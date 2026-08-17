from flask import Blueprint

def init_app(app):
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.legacy_routes import legacy_bp
    from app.routes.ambulance import ambulance_bp
    from app.routes.signal import signal_bp
    from app.routes.emergency import emergency_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(legacy_bp)
    app.register_blueprint(ambulance_bp)
    app.register_blueprint(signal_bp)
    app.register_blueprint(emergency_bp)
