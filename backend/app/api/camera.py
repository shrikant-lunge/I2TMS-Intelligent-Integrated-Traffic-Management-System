"""
Camera API - Camera control and video streaming.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
import cv2
import time
import logging
import os
import shutil
from pathlib import Path
from uuid import uuid4

from app.models.schemas import CameraStatusResponse, CameraMode
from app.models.database import save_plate_record, get_plate_records
from app.services.camera_service import camera_service
from app.services.detection_service import detect_vehicles
from app.services.plate_service import detect_plate
from app.services.ocr_service import read_plate
from app.core.pipeline import pipeline
from app.config import VIDEOS_DIR
from app.services.uploaded_anpr_service import OUTPUT_DIR, process_uploaded_video

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/camera", tags=["Camera"])

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mkv", ".mov", ".webm"}


def _resolve_video_source(source: str | None) -> str | None:
    """Resolve an uploaded video filename without allowing directory traversal."""
    if not source:
        return None

    # Uploaded files are addressed by their generated filename. Existing
    # absolute paths and camera/RTSP sources retain their previous behaviour.
    candidate_name = Path(str(source)).name
    if candidate_name == str(source):
        candidate = (VIDEOS_DIR / candidate_name).resolve()
        videos_root = VIDEOS_DIR.resolve()
        if candidate.parent == videos_root and candidate.is_file():
            return str(candidate)
    return str(source)


@router.post("/upload")
async def upload_video(video: UploadFile = File(...)):
    """Store a user-selected traffic video for playback and ANPR processing."""
    original_name = video.filename or "video.mp4"
    extension = Path(original_name).suffix.lower()
    if extension not in SUPPORTED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported video format. Use MP4, AVI, MKV, MOV, or WEBM.",
        )

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = f"upload_{uuid4().hex}{extension}"
    destination = (VIDEOS_DIR / stored_name).resolve()

    try:
        with destination.open("wb") as output:
            shutil.copyfileobj(video.file, output)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        logger.exception("Unable to save uploaded video")
        raise HTTPException(status_code=500, detail="Unable to save uploaded video") from exc
    finally:
        await video.close()

    return {
        "status": "ok",
        "filename": stored_name,
        "original_filename": original_name,
        "size_bytes": destination.stat().st_size,
        "message": "Video uploaded and ready for ANPR processing",
    }


@router.post("/anpr/scan")
async def scan_uploaded_video_with_anpr(source: str):
    """Run only the supplied standalone ANPR project for an uploaded video."""
    source_path = _resolve_video_source(source)
    if not source_path:
        raise HTTPException(status_code=400, detail="Select an uploaded video first")
    try:
        result = process_uploaded_video(Path(source_path))
    except (FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Supplied ANPR processing failed")
        raise HTTPException(status_code=500, detail=f"ANPR processing failed: {exc}") from exc
    return {
        "status": "ok",
        **result,
        "video_url": f"/api/camera/anpr-video/{result['video_filename']}",
        "message": f"ANPR model completed: {result['count']} recognized plates",
    }


@router.get("/anpr-video/{filename}")
async def serve_anpr_video(filename: str):
    """Serve a generated annotated ANPR recording."""
    video_path = (OUTPUT_DIR / Path(filename).name).resolve()
    if video_path.parent != OUTPUT_DIR.resolve() or not video_path.is_file():
        raise HTTPException(status_code=404, detail="ANPR video not found")
    return FileResponse(str(video_path), media_type="video/mp4")


@router.get("/anpr-feed/{filename}")
async def stream_anpr_video(filename: str):
    """Play the rendered ANPR video as MJPEG for browser-codec independence."""
    video_path = (OUTPUT_DIR / Path(filename).name).resolve()
    if video_path.parent != OUTPUT_DIR.resolve() or not video_path.is_file():
        raise HTTPException(status_code=404, detail="ANPR video not found")

    def generate():
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_delay = max(0.001, 1.0 / fps)
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                encoded, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if encoded:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + buffer.tobytes()
                        + b"\r\n"
                    )
                time.sleep(frame_delay)
        finally:
            cap.release()

    return StreamingResponse(
        generate(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.post("/start")
async def start_camera(source: str = None, mode: str = "LIVE_CAMERA"):
    """Start camera/video capture."""
    src = _resolve_video_source(source)
    if src is not None:
        try:
            src = int(src)
        except ValueError:
            pass
    elif mode.upper() == "VIDEO_FILE":
        candidates = sorted(VIDEOS_DIR.glob("*"))
        for candidate in candidates:
            if candidate.is_file():
                src = str(candidate)
                break

    success = camera_service.start(src)
    if not success:
        return {
            "status": "warning",
            "message": "Camera unavailable. No demo video found. Place a video in data/videos/",
            "mode": "UNAVAILABLE",
        }

    if not pipeline.running:
        pipeline.start()

    return {
        "status": "ok",
        "message": f"Camera started in {camera_service.mode} mode",
        "mode": camera_service.mode,
        "source": camera_service.source,
    }


@router.post("/stop")
async def stop_camera():
    """Stop camera/video capture."""
    pipeline.stop()
    camera_service.stop()
    return {"status": "ok", "message": "Camera and pipeline stopped"}


@router.get("/status", response_model=CameraStatusResponse)
async def camera_status():
    """Get camera status."""
    status = camera_service.get_status()
    return CameraStatusResponse(
        running=status["running"],
        mode=CameraMode(status["mode"]) if status["mode"] in CameraMode.__members__.values() else CameraMode.UNAVAILABLE,
        source=status["source"],
        frame_count=status["frame_count"],
        fps=status["fps"],
    )


@router.get("/feed")
async def video_feed():
    """MJPEG video stream with detection overlays."""
    def generate():
        while True:
            frame = pipeline.current_frame
            if frame is not None:
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n'
                    + buffer.tobytes()
                    + b'\r\n'
                )
            time.sleep(0.033)  # ~30 fps

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/vehicles")
async def get_vehicles():
    """Get currently detected and tracked vehicles."""
    return {
        "vehicles": pipeline.current_vehicles,
        "count": len(pipeline.current_vehicles),
        "corridor_polygon": pipeline.corridor_polygon,
    }


@router.post("/scan")
async def scan_plates(source: str = None, mode: str = "LIVE_CAMERA"):
    """Scan a live source or a recorded file and persist recognized number plates."""
    selected_source = _resolve_video_source(source)

    if not selected_source:
        if mode.upper() == "VIDEO_FILE":
            candidates = sorted(VIDEOS_DIR.glob("*"))
            for candidate in candidates:
                if candidate.is_file():
                    selected_source = str(candidate)
                    break
        else:
            selected_source = "0"

    if not selected_source:
        raise HTTPException(status_code=400, detail="No camera or video source supplied")

    try:
        cap = cv2.VideoCapture(int(selected_source)) if selected_source.isdigit() else cv2.VideoCapture(selected_source)
    except Exception:
        cap = cv2.VideoCapture(selected_source)

    if not cap.isOpened():
        raise HTTPException(status_code=400, detail=f"Unable to open source: {selected_source}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) if cap.get(cv2.CAP_PROP_FRAME_COUNT) > 0 else 0
    max_frames = total_frames if mode.upper() == "VIDEO_FILE" and total_frames > 0 else 240
    plates = []
    seen = set()
    frame_count = 0

    def add_plate_result(plate_number, confidence, vehicle_type=None):
        plate_number = (plate_number or '').strip().upper()
        if not plate_number or plate_number in seen:
            return
        seen.add(plate_number)
        plates.append({
            "plate_number": plate_number,
            "plate_confidence": confidence,
            "source_mode": mode.upper(),
            "source_value": selected_source,
            "vehicle_type": vehicle_type,
        })
        save_plate_record(
            plate_number=plate_number,
            plate_confidence=confidence,
            source_mode=mode.upper(),
            source_value=selected_source,
            vehicle_type=vehicle_type,
            status="RECOGNIZED",
            notes="Detected from camera scan",
        )

    def process_plate_result(plate_result, fallback_vehicle_type=None):
        if plate_result is None:
            return False

        ocr = read_plate(plate_result["plate_crop"])
        plate_number = (ocr.get("normalized_text") or ocr.get("raw_text") or "").strip().upper()
        if ocr.get("status") in {"OK", "NEEDS_REVIEW"} and plate_number:
            add_plate_result(plate_number, ocr.get("confidence"), fallback_vehicle_type)
            return True
        return False

    try:
        while frame_count < max_frames:
            ok, frame = cap.read()
            if not ok:
                if mode.upper() == "VIDEO_FILE":
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    if total_frames > 0:
                        break
                    continue
                break

            detections = detect_vehicles(frame)
            processed_vehicle = False

            for detection in detections:
                x1, y1, x2, y2 = detection.get("bbox", [0, 0, 0, 0])
                vehicle_crop = frame[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
                if vehicle_crop.size == 0:
                    continue

                plate_result = detect_plate(vehicle_crop)
                if plate_result is not None:
                    # use ensemble extractor for better OCR on challenging crops
                    from app.services.plate_ocr_ensemble import extract_plate_number
                    ensemble = extract_plate_number(plate_result["plate_crop"]) if plate_result.get("plate_crop") is not None else None
                    if ensemble is not None and ensemble.get("plate_number"):
                        add_plate_result(ensemble.get("plate_number"), ensemble.get("confidence"), detection.get("class_name"))
                        processed_vehicle = True
                        continue
                if process_plate_result(plate_result, detection.get("class_name")):
                    processed_vehicle = True

            if not processed_vehicle:
                frame_plate = detect_plate(frame)
                process_plate_result(frame_plate, "detected_from_frame")

            frame_count += 1
            if mode.upper() == "VIDEO_FILE" and total_frames > 0 and cap.get(cv2.CAP_PROP_POS_FRAMES) >= total_frames:
                break

        return {
            "status": "ok",
            "mode": mode.upper(),
            "source": selected_source,
            "plates": plates,
            "count": len(plates),
            "message": f"Detected {len(plates)} plate numbers from {selected_source}",
        }
    finally:
        cap.release()


@router.get("/plates")
async def get_plate_records_api():
    """Return all stored plate numbers for the selected camera/video mode."""
    records = get_plate_records(limit=200)
    return {
        "plates": [
            {
                "id": record.id,
                "plate_number": record.plate_number,
                "plate_confidence": record.plate_confidence,
                "source_mode": record.source_mode,
                "source_value": record.source_value,
                "vehicle_type": record.vehicle_type,
                "status": record.status,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
            for record in records
        ],
        "count": len(records),
    }
