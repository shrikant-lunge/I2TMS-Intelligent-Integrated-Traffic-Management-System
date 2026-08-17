"""
Configuration module - loads settings from environment variables.
Merges I2TMS Flask config and TMS pipeline config.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24))
    
    # ── Database ────────────────────────────────────────────────────────────
    # TARGET: Supabase PostgreSQL
    #   Set DATABASE_URL in .env to your Supabase connection string, e.g.:
    #     DATABASE_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
    #   The project ref is the subdomain of SUPABASE_URL (agdzmafsgoyyosigduct).
    #   Find the password in Supabase → Project Settings → Database → Connection string.
    #
    # FALLBACK: SQLite (used when DATABASE_URL is not set)
    _db_url = os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR}/database/i2tms.db"
    # Supabase uses "postgres://" scheme in some contexts; SQLAlchemy requires "postgresql://"
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Connection pool settings for PostgreSQL (ignored by SQLite)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,        # Detect stale connections
        "pool_recycle": 300,          # Recycle connections every 5 minutes
        "connect_args": (
            {"sslmode": "require"} if _db_url.startswith("postgresql") else {}
        ),
    }
    
    # --- Project Paths (from TMS) ---
    DATA_DIR = BASE_DIR / "data"
    EVIDENCE_DIR = DATA_DIR / "evidence"
    PLATES_DIR = DATA_DIR / "plates"
    VIDEOS_DIR = DATA_DIR / "videos"
    MODELS_DIR = BASE_DIR / "models"
    EASYOCR_DIR = DATA_DIR / "easyocr"

    # --- Mode ---
    DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"

    # --- Camera ---
    _camera_src = os.getenv("CAMERA_SOURCE", "0")
    try:
        CAMERA_SOURCE = int(_camera_src)
    except ValueError:
        CAMERA_SOURCE = _camera_src  # Path to video file
    FRAME_SKIP = int(os.getenv("FRAME_SKIP", "2"))

    # --- YOLO ---
    YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
    MIN_DETECTION_CONFIDENCE = float(os.getenv("MIN_DETECTION_CONFIDENCE", "0.5"))

    # --- Tracking ---
    MAX_DISAPPEARED_FRAMES = int(os.getenv("MAX_DISAPPEARED_FRAMES", "30"))
    MAX_TRACK_DISTANCE = float(os.getenv("MAX_TRACK_DISTANCE", "80"))

    # --- Emergency Corridor (ratios of frame dimensions) ---
    CORRIDOR_TOP_WIDTH_RATIO = float(os.getenv("CORRIDOR_TOP_WIDTH_RATIO", "0.3"))
    CORRIDOR_BOTTOM_WIDTH_RATIO = float(os.getenv("CORRIDOR_BOTTOM_WIDTH_RATIO", "0.8"))
    CORRIDOR_TOP_Y_RATIO = float(os.getenv("CORRIDOR_TOP_Y_RATIO", "0.3"))
    CORRIDOR_BOTTOM_Y_RATIO = float(os.getenv("CORRIDOR_BOTTOM_Y_RATIO", "0.95"))

    # --- Violation Thresholds ---
    MIN_BLOCKING_TIME = float(os.getenv("MIN_BLOCKING_TIME", "3"))  # seconds
    MIN_MOVEMENT_THRESHOLD = float(os.getenv("MIN_MOVEMENT_THRESHOLD", "15"))  # pixels

    # --- Plate / OCR ---
    MIN_PLATE_CONFIDENCE = float(os.getenv("MIN_PLATE_CONFIDENCE", "0.4"))
    OCR_ENGINE = os.getenv("OCR_ENGINE", "easyocr")
    PLATE_DETECTOR_ENABLED = os.getenv("PLATE_DETECTOR_ENABLED", "true").lower() == "true"
    PLATE_DETECTION_CONFIDENCE = float(os.getenv("PLATE_DETECTION_CONFIDENCE", "0.35"))

    # Dedicated YOLOv8 ANPR detector
    _plate_model = os.getenv(
        "PLATE_MODEL",
        "../TMS/backend/anpr_demo/models/license_plate_detector.pt",
    ).strip()
    PLATE_MODEL = Path(_plate_model)
    if not PLATE_MODEL.is_absolute():
        PLATE_MODEL = (BASE_DIR / PLATE_MODEL).resolve()

    # --- OSRM ---
    OSRM_URL = os.getenv("OSRM_URL", "https://router.project-osrm.org")

    # --- YOLO COCO classes of interest ---
    VEHICLE_CLASSES = {
        2: "car",
        3: "motorcycle",
        5: "bus",
        7: "truck",
    }

# Expose at module level for compatibility with TMS code
SECRET_KEY = Config.SECRET_KEY
SQLALCHEMY_DATABASE_URI = Config.SQLALCHEMY_DATABASE_URI
SQLALCHEMY_TRACK_MODIFICATIONS = Config.SQLALCHEMY_TRACK_MODIFICATIONS
SQLALCHEMY_ENGINE_OPTIONS = Config.SQLALCHEMY_ENGINE_OPTIONS
DATA_DIR = Config.DATA_DIR
EVIDENCE_DIR = Config.EVIDENCE_DIR
PLATES_DIR = Config.PLATES_DIR
VIDEOS_DIR = Config.VIDEOS_DIR
MODELS_DIR = Config.MODELS_DIR
EASYOCR_DIR = Config.EASYOCR_DIR
DEMO_MODE = Config.DEMO_MODE
CAMERA_SOURCE = Config.CAMERA_SOURCE
FRAME_SKIP = Config.FRAME_SKIP
YOLO_MODEL = Config.YOLO_MODEL
MIN_DETECTION_CONFIDENCE = Config.MIN_DETECTION_CONFIDENCE
MAX_DISAPPEARED_FRAMES = Config.MAX_DISAPPEARED_FRAMES
MAX_TRACK_DISTANCE = Config.MAX_TRACK_DISTANCE
CORRIDOR_TOP_WIDTH_RATIO = Config.CORRIDOR_TOP_WIDTH_RATIO
CORRIDOR_BOTTOM_WIDTH_RATIO = Config.CORRIDOR_BOTTOM_WIDTH_RATIO
CORRIDOR_TOP_Y_RATIO = Config.CORRIDOR_TOP_Y_RATIO
CORRIDOR_BOTTOM_Y_RATIO = Config.CORRIDOR_BOTTOM_Y_RATIO
MIN_BLOCKING_TIME = Config.MIN_BLOCKING_TIME
MIN_MOVEMENT_THRESHOLD = Config.MIN_MOVEMENT_THRESHOLD
MIN_PLATE_CONFIDENCE = Config.MIN_PLATE_CONFIDENCE
OCR_ENGINE = Config.OCR_ENGINE
PLATE_DETECTOR_ENABLED = Config.PLATE_DETECTOR_ENABLED
PLATE_DETECTION_CONFIDENCE = Config.PLATE_DETECTION_CONFIDENCE
PLATE_MODEL = Config.PLATE_MODEL
OSRM_URL = Config.OSRM_URL
VEHICLE_CLASSES = Config.VEHICLE_CLASSES
BACKEND_ROOT = BASE_DIR
