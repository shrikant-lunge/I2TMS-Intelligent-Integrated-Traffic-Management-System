"""
Configuration module - loads settings from environment variables.
All configurable values are centralized here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load env files in a predictable order so the backend-specific settings win.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent

# Keep Ultralytics runtime settings inside this project. Some Windows profiles
# deny access to its default roaming-AppData location, which otherwise stops
# ANPR model loading before a video can be processed.
ULTRALYTICS_CONFIG_DIR = BACKEND_ROOT / ".ultralytics"
ULTRALYTICS_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(ULTRALYTICS_CONFIG_DIR))

for env_file in [
    PROJECT_ROOT / ".env",
    BACKEND_ROOT / ".env",
    PROJECT_ROOT / ".env.example",
    BACKEND_ROOT / ".env.example",
]:
    if env_file.exists():
        load_dotenv(env_file)

# --- Project Paths ---
DATA_DIR = PROJECT_ROOT / "data"
EVIDENCE_DIR = DATA_DIR / "evidence"
PLATES_DIR = DATA_DIR / "plates"
VIDEOS_DIR = DATA_DIR / "videos"
MODELS_DIR = PROJECT_ROOT / "models"

# Create directories
for d in [DATA_DIR, EVIDENCE_DIR, PLATES_DIR, VIDEOS_DIR, MODELS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

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

# Dedicated YOLOv8 ANPR detector imported from the supplied ANPR project.
# A relative value is resolved from the TMS project root so it works whether
# the backend is launched from the repository root or from ``backend/``.
_plate_model = os.getenv(
    "PLATE_MODEL",
    "backend/anpr_demo/models/license_plate_detector.pt",
).strip()
PLATE_MODEL = Path(_plate_model)
if not PLATE_MODEL.is_absolute():
    PLATE_MODEL = (PROJECT_ROOT / PLATE_MODEL).resolve()

# --- Database ---
_db_url = os.getenv("DATABASE_URL")
if _db_url:
    _db_url = _db_url.strip()
    if _db_url.startswith("sqlite:///") and not _db_url.startswith("sqlite:////"):
        _relative_db_path = _db_url.replace("sqlite:///", "", 1)
        if _relative_db_path.startswith("./"):
            _relative_db_path = _relative_db_path[2:]
        _relative_db_path = _relative_db_path.replace("/", os.sep)
        candidate = (PROJECT_ROOT / _relative_db_path).resolve()
        _db_url = f"sqlite:///{candidate.as_posix()}"
    DATABASE_URL = _db_url
else:
    DATABASE_URL = f"sqlite:///{(DATA_DIR / 'tms.db').resolve().as_posix()}"

# --- Server ---
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# --- OSRM ---
OSRM_URL = os.getenv("OSRM_URL", "https://router.project-osrm.org")

# --- YOLO COCO classes of interest ---
VEHICLE_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
