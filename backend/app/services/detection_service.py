"""
Detection Service - YOLO-based vehicle detection.
"""

import logging
import threading
import numpy as np
from typing import List, Optional, Tuple

from app.config import YOLO_MODEL, MIN_DETECTION_CONFIDENCE, VEHICLE_CLASSES

logger = logging.getLogger(__name__)

# Lazy-loaded model
_model = None
_model_loaded = False
_model_error: Optional[str] = None
_model_lock = threading.RLock()


def _load_model():
    """Lazy-load YOLO model."""
    global _model, _model_loaded, _model_error
    with _model_lock:
        if _model_loaded:
            return _model

        try:
            from ultralytics import YOLO
            _model = YOLO(YOLO_MODEL)
            _model_loaded = True
            logger.info(f"YOLO vehicle model loaded: {YOLO_MODEL}")
            return _model
        except Exception as e:
            _model_error = str(e)
            _model_loaded = True  # Don't retry
            logger.error(f"Failed to load YOLO vehicle model: {e}")
            return None


def detect_vehicles(frame: np.ndarray) -> List[dict]:
    """
    Detect vehicles in a frame using YOLO.

    Returns list of detections:
    [
        {
            "class_id": int,
            "class_name": str,
            "confidence": float,
            "bbox": [x1, y1, x2, y2],
            "center": [cx, cy],
        },
        ...
    ]
    """
    model = _load_model()
    if model is None:
        return []

    try:
        # The live playback pipeline and video scanner can run concurrently.
        # Ultralytics model fusion is not safe while another thread is loading
        # or using the same instance, so serialize access to this shared model.
        with _model_lock:
            results = model(frame, conf=MIN_DETECTION_CONFIDENCE, verbose=False)
        detections = []

        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue

            for box in boxes:
                cls_id = int(box.cls[0])
                if cls_id not in VEHICLE_CLASSES:
                    continue

                conf = float(box.conf[0])
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                detections.append({
                    "class_id": cls_id,
                    "class_name": VEHICLE_CLASSES[cls_id],
                    "confidence": round(conf, 3),
                    "bbox": [x1, y1, x2, y2],
                    "center": [cx, cy],
                })

        return detections

    except Exception as e:
        logger.error(f"Detection error: {e}")
        return []


def is_model_available() -> Tuple[bool, Optional[str]]:
    """Check if YOLO model is available."""
    model = _load_model()
    if model is not None:
        return True, None
    return False, _model_error
