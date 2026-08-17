import os
from datetime import timedelta
from flask import Flask

from app.config import Config
from app.extensions import db

def create_app(config_class=Config):
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(config_class)
    app.permanent_session_lifetime = timedelta(days=30)
    
    # Initialize extensions
    db.init_app(app)

    with app.app_context():
        from app.models import Junction  # imports all models into metadata before create_all

        db.create_all()
        from datetime import datetime

        if not Junction.query.filter_by(name="Rahate Colony Square").first():
            db.session.add(
                Junction(
                    name="Rahate Colony Square",
                    status="moderate",
                    last_updated=datetime.utcnow(),
                )
            )
            db.session.commit()
    
    # Ensure data directories exist
    for d in [Config.DATA_DIR, Config.EVIDENCE_DIR, Config.PLATES_DIR, Config.VIDEOS_DIR, Config.MODELS_DIR, Config.EASYOCR_DIR]:
        os.makedirs(d, exist_ok=True)
        
    os.environ.setdefault("EASYOCR_MODULE_PATH", str(Config.EASYOCR_DIR))
    
    # Register blueprints
    from app.routes import init_app as init_routes
    init_routes(app)
    
    return app
