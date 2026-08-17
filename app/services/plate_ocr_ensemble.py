"""
Ensemble OCR helper for plate crops.

This module implements an original ensemble strategy that
tries multiple scales and small rotations of a candidate plate
crop, delegates OCR to the existing `read_plate()` (which includes
preprocessing), and selects the best normalized plate text using
validation heuristics.

This is an independent implementation and does not copy code
from external repositories.
"""

from typing import List, Dict, Optional, Tuple
import cv2
import numpy as np
import logging

from app.services.ocr_service import read_plate, validate_plate_text

logger = logging.getLogger(__name__)


def _rotate_image(img: np.ndarray, angle: float) -> np.ndarray:
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated


def _scale_image(img: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return img
    h, w = img.shape[:2]
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def extract_plate_number(
    plate_crop: np.ndarray,
    rotations: List[float] = (0.0, -5.0, 5.0),
    scales: List[float] = (1.0, 1.5, 2.0),
    top_k: int = 5,
) -> Optional[Dict[str, object]]:
    """
    Run an ensemble OCR over `plate_crop` and return the best candidate.

    Returns a dict:
      {
        'plate_number': str,
        'confidence': float,
        'status': str,
        'candidates': [ { 'text', 'confidence', 'status', 'scale', 'rotation' }, ... ]
      }

    If no text is found, returns None.
    """
    if plate_crop is None or plate_crop.size == 0:
        return None

    candidates: List[Dict] = []

    for scale in scales:
        try:
            scaled = _scale_image(plate_crop, scale)
        except Exception:
            scaled = plate_crop

        for rot in rotations:
            try:
                img = _rotate_image(scaled, rot) if rot != 0.0 else scaled
            except Exception:
                img = scaled

            try:
                o = read_plate(img)
            except Exception as e:
                logger.debug("OCR error on candidate: %s", e)
                continue

            text = (o.get("normalized_text") or o.get("raw_text") or "").strip().upper()
            conf = float(o.get("confidence") or 0.0)
            status = o.get("status")

            if not text:
                continue

            candidates.append({
                "text": text,
                "confidence": conf,
                "status": status,
                "scale": scale,
                "rotation": rot,
            })

    if not candidates:
        return None

    # Prefer validated plate texts first (validate_plate_text)
    validated = [c for c in candidates if validate_plate_text(c["text"])]
    if validated:
        # choose highest confidence among validated ones
        best = max(validated, key=lambda c: c["confidence"])
    else:
        # otherwise choose highest confidence overall but prefer longer strings
        candidates.sort(key=lambda c: (c["confidence"], len(c["text"])), reverse=True)
        best = candidates[0]

    result = {
        "plate_number": best["text"],
        "confidence": best["confidence"],
        "status": best.get("status"),
        "candidates": candidates[:top_k],
    }

    return result
