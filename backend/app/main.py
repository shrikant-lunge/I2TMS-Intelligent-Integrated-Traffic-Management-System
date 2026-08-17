"""
Smart Ambulance Emergency Corridor - FastAPI Main Application
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from app.config import FRONTEND_URL, EVIDENCE_DIR, DATA_DIR, DEMO_MODE
from app.models.database import init_db
from app.api import emergency, camera, violations, challans, routes

# =============================================================================
# Logging setup
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# =============================================================================
# FastAPI App
# =============================================================================
app = FastAPI(
    title="Smart Ambulance Emergency Corridor System",
    description=(
        "Ambulance emergency-corridor enforcement system with YOLO vehicle detection, "
        "tracking, number plate recognition, and simulated e-challan generation."
    ),
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Include API routers
# =============================================================================
app.include_router(emergency.router)
app.include_router(camera.router)
app.include_router(violations.router)
app.include_router(challans.router)
app.include_router(routes.router)


# =============================================================================
# Evidence static file serving
# =============================================================================
@app.get("/api/evidence/{violation_id}/{filename}")
async def serve_evidence(violation_id: str, filename: str):
    """Serve evidence images."""
    file_path = EVIDENCE_DIR / violation_id / filename
    if file_path.exists():
        return FileResponse(str(file_path))
    return JSONResponse(status_code=404, content={"detail": "File not found"})


# =============================================================================
# Health / Info
# =============================================================================
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Smart Ambulance Emergency Corridor System"}


@app.get("/api/info")
async def info():
    from app.services.detection_service import is_model_available
    from app.services.ocr_service import is_ocr_available
    from app.services.plate_service import is_dedicated_plate_detector_available
    from app.config import PLATE_MODEL

    yolo_ok, yolo_err = is_model_available()
    ocr_ok, ocr_err = is_ocr_available()
    plate_model_ok, plate_model_err = is_dedicated_plate_detector_available()

    return {
        "service": "Smart Ambulance Emergency Corridor System",
        "version": "1.0.0",
        "demo_mode": DEMO_MODE,
        "yolo_available": yolo_ok,
        "yolo_error": yolo_err,
        "ocr_available": ocr_ok,
        "ocr_error": ocr_err,
        "anpr_plate_model": str(PLATE_MODEL),
        "anpr_plate_model_available": plate_model_ok,
        "anpr_plate_model_error": plate_model_err,
    }


# =============================================================================
# Startup
# =============================================================================
@app.on_event("startup")
async def startup():
    logger.info("=" * 60)
    logger.info("Smart Ambulance Emergency Corridor System - Starting")
    logger.info("=" * 60)

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Ensure directories exist
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "videos").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "plates").mkdir(parents=True, exist_ok=True)

    if DEMO_MODE:
        logger.info("Running in DEMO MODE")

    logger.info(f"Frontend URL: {FRONTEND_URL}")
    logger.info("API docs available at /docs")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown():
    from app.core.pipeline import pipeline
    from app.services.camera_service import camera_service

    pipeline.stop()
    camera_service.stop()
    logger.info("Application shutdown complete")
