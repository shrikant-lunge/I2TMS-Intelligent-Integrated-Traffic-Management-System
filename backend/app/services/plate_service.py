"""
Plate Service - Number plate detection from vehicle crops.

The supplied YOLOv8 ANPR model is used as the primary detector.  The original
contour and morphology implementation remains in place as a safe fallback for
installations where the optional model is unavailable.
"""

import logging
import threading
from typing import Optional, Tuple, List

import cv2
import numpy as np

from app.config import (
    PLATE_DETECTOR_ENABLED,
    PLATE_DETECTION_CONFIDENCE,
    PLATE_MODEL,
)

logger = logging.getLogger(__name__)

_plate_model = None
_plate_model_loaded = False
_plate_model_error: Optional[str] = None
_plate_model_lock = threading.RLock()


def _load_plate_model():
    """Load the dedicated ANPR model once, without blocking fallback detection."""
    global _plate_model, _plate_model_loaded, _plate_model_error
    with _plate_model_lock:
        if _plate_model_loaded:
            return _plate_model

        _plate_model_loaded = True
        if not PLATE_DETECTOR_ENABLED:
            logger.info("Dedicated plate detector disabled by configuration")
            return None
        if not PLATE_MODEL.is_file():
            _plate_model_error = f"Plate model not found: {PLATE_MODEL}"
            logger.warning("%s; using contour fallback", _plate_model_error)
            return None

        try:
            from ultralytics import YOLO
            _plate_model = YOLO(str(PLATE_MODEL))
            logger.info("Dedicated ANPR plate detector loaded: %s", PLATE_MODEL)
        except Exception as exc:
            _plate_model_error = str(exc)
            logger.warning("Could not load dedicated plate detector: %s", exc)
        return _plate_model


def _detect_plate_with_yolo(vehicle_crop: np.ndarray) -> Optional[dict]:
    """Return the highest-confidence YOLO plate detection in a vehicle crop."""
    model = _load_plate_model()
    if model is None:
        return None

    try:
        with _plate_model_lock:
            result = model(
                vehicle_crop,
                conf=PLATE_DETECTION_CONFIDENCE,
                verbose=False,
            )[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return None

        best = max(boxes, key=lambda box: float(box.conf[0]))
        confidence = float(best.conf[0])
        x1, y1, x2, y2 = [int(value) for value in best.xyxy[0].tolist()]
        h, w = vehicle_crop.shape[:2]

        # Include a small border because OCR is less reliable when characters
        # touch the crop edge.  Coordinates remain relative to vehicle_crop.
        padding = 3
        x1, y1 = max(0, x1 - padding), max(0, y1 - padding)
        x2, y2 = min(w, x2 + padding), min(h, y2 + padding)
        plate_crop = vehicle_crop[y1:y2, x1:x2]
        if plate_crop.size == 0:
            return None

        return {
            "plate_bbox": [x1, y1, x2, y2],
            "plate_crop": plate_crop,
            "confidence": round(confidence, 3),
            "detector": "yolov8_anpr",
        }
    except Exception as exc:
        logger.warning("Dedicated plate detection failed: %s", exc)
        return None


def is_dedicated_plate_detector_available() -> Tuple[bool, Optional[str]]:
    """Expose detector health without making ANPR fallback unavailable."""
    model = _load_plate_model()
    if model is not None:
        return True, None
    return False, _plate_model_error


def detect_plate(vehicle_crop: np.ndarray) -> Optional[dict]:
    """
    Detect number plate in a vehicle crop image.

    Returns:
        {
            "plate_bbox": [x1, y1, x2, y2],  # relative to crop
            "plate_crop": np.ndarray,
            "confidence": float,
        }
        or None if no plate found.
    """
    if vehicle_crop is None or vehicle_crop.size == 0:
        return None

    try:
        h, w = vehicle_crop.shape[:2]
        if h < 20 or w < 20:
            return None

        # The supplied project detects plates with its trained YOLOv8 model.
        # Keep the established contour method below as a fallback, not a
        # replacement, so existing feeds retain their previous behaviour.
        yolo_result = _detect_plate_with_yolo(vehicle_crop)
        if yolo_result is not None:
            return yolo_result

        # Convert to grayscale
        gray = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGR2GRAY)

        # Apply bilateral filter to reduce noise while keeping edges
        filtered = cv2.bilateralFilter(gray, 11, 17, 17)

        # Edge detection
        edges = cv2.Canny(filtered, 30, 200)

        # Dilate to connect edges
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=1)

        # Find contours
        contours, _ = cv2.findContours(
            edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )

        candidates = []

        for contour in contours:
            area = cv2.contourArea(contour)
            # Filter by area (plate should be reasonable size relative to vehicle)
            # Relaxed to improve recall on small/partial crops
            min_area = h * w * 0.005  # At least 0.5% of vehicle crop
            max_area = h * w * 0.5    # At most 50% of vehicle crop

            if area < min_area or area > max_area:
                continue

            # Approximate contour to polygon
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

            # Plates are roughly rectangular (4 corners)
            if len(approx) >= 4 and len(approx) <= 8:
                x, y, bw, bh = cv2.boundingRect(approx)
                aspect_ratio = bw / max(bh, 1)

                # Plates vary by country and viewing angle; accept wider aspect ratios
                if 1.2 <= aspect_ratio <= 8.0:
                    # Plate is typically in lower half of vehicle
                    center_y = y + bh / 2
                    position_score = center_y / h  # Higher = lower in image = better

                    confidence = min(1.0, (
                        0.3 * min(aspect_ratio / 3.0, 1.0)  # Aspect ratio score
                        + 0.3 * position_score               # Position score
                        + 0.2 * min(area / (h * w * 0.05), 1.0)  # Size score
                        + 0.2 * (1.0 if len(approx) == 4 else 0.5)  # Shape score
                    ))

                    candidates.append({
                        "bbox": [x, y, x + bw, y + bh],
                        "confidence": confidence,
                        "area": area,
                    })

        if not candidates:
            # Fallback: try to find plate using morphological operations
            return _morphological_plate_detection(vehicle_crop, gray)

        # Pick the best candidate
        candidates.sort(key=lambda c: c["confidence"], reverse=True)
        best = candidates[0]

        x1, y1, x2, y2 = best["bbox"]
        # Add small padding
        pad = 3
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(w, x2 + pad)
        y2 = min(h, y2 + pad)

        plate_crop = vehicle_crop[y1:y2, x1:x2]
        if plate_crop.size == 0:
            return None

        return {
            "plate_bbox": [x1, y1, x2, y2],
            "plate_crop": plate_crop,
            "confidence": round(best["confidence"], 3),
            "detector": "contour",
        }

    except Exception as e:
        logger.error(f"Plate detection error: {e}")
        return None


def _morphological_plate_detection(
    vehicle_crop: np.ndarray, gray: np.ndarray
) -> Optional[dict]:
    """Fallback plate detection using morphological operations."""
    try:
        h, w = gray.shape

        # Focus on lower 2/3 of vehicle (where plates usually are)
        roi_y = h // 3
        roi = gray[roi_y:, :]

        # Blackhat to find dark text on light background
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 7))
        blackhat = cv2.morphologyEx(roi, cv2.MORPH_BLACKHAT, kernel)

        # Threshold
        _, thresh = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
            x, y, bw, bh = cv2.boundingRect(contour)
            aspect = bw / max(bh, 1)
            area = bw * bh

            # Loosen constraints to allow partial/angled plates
            if 1.2 <= aspect <= 8.0 and area > (h * w * 0.003):
                actual_y = y + roi_y
                pad = 5
                x1 = max(0, x - pad)
                y1 = max(0, actual_y - pad)
                x2 = min(w, x + bw + pad)
                y2 = min(h, actual_y + bh + pad)

                plate_crop = vehicle_crop[y1:y2, x1:x2]
                if plate_crop.size == 0:
                    continue

                return {
                    "plate_bbox": [x1, y1, x2, y2],
                    "plate_crop": plate_crop,
                    "confidence": 0.3,  # Lower confidence for fallback
                    "detector": "morphology",
                }

        return None
    except Exception as e:
        logger.error(f"Morphological plate detection error: {e}")
        return None
