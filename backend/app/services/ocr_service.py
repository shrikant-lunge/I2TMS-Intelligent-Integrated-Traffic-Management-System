"""
OCR Service - Number plate text recognition using EasyOCR.
Includes preprocessing and Indian plate format validation.
"""

import re
import logging
from typing import Optional, Tuple

import cv2
import numpy as np

from app.config import MIN_PLATE_CONFIDENCE

logger = logging.getLogger(__name__)

# Lazy-loaded OCR reader
_reader = None
_reader_loaded = False
_reader_error: Optional[str] = None

# Indian vehicle registration format patterns
# Standard: XX 00 XX 0000  (e.g., MH 12 AB 1234)
# Variations: XX 00 X 0000, XX 00 XX 000
INDIAN_PLATE_PATTERNS = [
    r'^[A-Z]{2}\d{2}[A-Z]{1,3}\d{1,4}$',   # Standard format
    r'^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{1,4}$',  # Flexible digits
]


def _load_reader():
    """Lazy-load EasyOCR reader."""
    global _reader, _reader_loaded, _reader_error
    if _reader_loaded:
        return _reader

    try:
        import easyocr
        _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        _reader_loaded = True
        logger.info("EasyOCR reader loaded")
        return _reader
    except Exception as e:
        _reader_error = str(e)
        _reader_loaded = True
        logger.error(f"Failed to load EasyOCR: {e}")
        return None


def preprocess_plate(plate_image: np.ndarray) -> np.ndarray:
    """Preprocess plate image for better OCR accuracy."""
    if plate_image is None or plate_image.size == 0:
        return plate_image

    img = plate_image.copy()

    # Resize to consistent height (larger to help EasyOCR on small crops)
    target_height = 120
    h, w = img.shape[:2]
    if h > 0:
        scale = target_height / h
        img = cv2.resize(img, (int(w * scale), target_height), interpolation=cv2.INTER_CUBIC)

    # Convert to grayscale if needed
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # CLAHE for contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Denoise more aggressively then sharpen
    denoised = cv2.fastNlMeansDenoising(enhanced, h=7)
    denoised = cv2.medianBlur(denoised, 3)

    # Sharpen slightly
    kernel = np.array([[-1, -1, -1], [-1, 10, -1], [-1, -1, -1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)

    # Morphological closing to join broken strokes
    kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(sharpened, cv2.MORPH_CLOSE, kernel2, iterations=1)

    # Adaptive threshold
    thresh = cv2.adaptiveThreshold(
        closed, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    return thresh


def read_plate(plate_image: np.ndarray) -> dict:
    """
    Perform OCR on a plate image.

    Returns:
        {
            "raw_text": str,
            "normalized_text": str,
            "confidence": float,
            "valid": bool,
            "status": str,  # "OK", "NEEDS_REVIEW", "INVALID"
        }
    """
    result = {
        "raw_text": "",
        "normalized_text": "",
        "confidence": 0.0,
        "valid": False,
        "status": "INVALID",
    }

    reader = _load_reader()
    if reader is None:
        result["status"] = "OCR_UNAVAILABLE"
        logger.warning("OCR unavailable - plate requires manual review")
        return result

    try:
        # Preprocess
        processed = preprocess_plate(plate_image)

        # Run OCR - try both original and processed
        ocr_results = []

        # Try processed image
        res1 = reader.readtext(processed, detail=1, paragraph=False)
        ocr_results.extend(res1)

        # Also try original for comparison
        res2 = reader.readtext(plate_image, detail=1, paragraph=False)
        ocr_results.extend(res2)

        if not ocr_results:
            result["status"] = "NO_TEXT_FOUND"
            return result

        # Combine all detected text and pick best
        best_text = ""
        best_conf = 0.0

        for detection in ocr_results:
            if len(detection) >= 3:
                _, text, conf = detection[:3]
            elif len(detection) == 2:
                text, conf = detection
            else:
                continue

            if conf > best_conf:
                best_text = text
                best_conf = conf

        if not best_text:
            result["status"] = "NO_TEXT_FOUND"
            return result

        result["raw_text"] = best_text
        result["confidence"] = round(float(best_conf), 3)

        # Normalize
        normalized = normalize_plate_text(best_text)
        result["normalized_text"] = normalized

        # Validate
        is_valid = validate_plate_text(normalized)
        result["valid"] = is_valid

        if is_valid and best_conf >= MIN_PLATE_CONFIDENCE:
            result["status"] = "OK"
        elif is_valid and best_conf < MIN_PLATE_CONFIDENCE:
            result["status"] = "NEEDS_REVIEW"
        elif not is_valid and best_conf >= 0.3:
            result["status"] = "NEEDS_REVIEW"
        else:
            result["status"] = "INVALID"

        logger.info(
            f"OCR result: raw='{best_text}', normalized='{normalized}', "
            f"conf={best_conf:.2f}, valid={is_valid}, status={result['status']}"
        )

        return result

    except Exception as e:
        logger.error(f"OCR error: {e}")
        result["status"] = "OCR_ERROR"
        return result


def normalize_plate_text(text: str) -> str:
    """Normalize plate text - remove spaces, special chars, uppercase."""
    # Remove all non-alphanumeric characters
    normalized = re.sub(r'[^A-Za-z0-9]', '', text)
    # Uppercase
    normalized = normalized.upper()

    # Common OCR substitutions
    replacements = {
        'O': '0',  # Only when in digit positions
        'I': '1',
        'S': '5',
        'Z': '2',
        'B': '8',
    }

    # Apply substitutions only in expected digit positions
    # Indian format: LL DD LL DDDD  (L=letter, D=digit)
    # We only fix obvious ones
    if len(normalized) >= 4:
        # First two should be letters - fix digits that should be letters
        fixed = list(normalized)

        # Position 2-3 should be digits (state district code)
        for i in [2, 3]:
            if i < len(fixed) and fixed[i] in replacements:
                # Only replace if it looks like it should be a digit
                if not fixed[i].isdigit():
                    fixed[i] = replacements.get(fixed[i], fixed[i])

        normalized = ''.join(fixed)

    return normalized


def validate_plate_text(text: str) -> bool:
    """Accept general alphanumeric plate text instead of only Indian formats."""
    if not text:
        return False

    text = text.strip().upper()
    if len(text) < 4 or len(text) > 15:
        return False

    # Reject clearly invalid strings like all digits or all letters
    if text.isdigit() or text.isalpha():
        return False

    # Must contain at least one letter and one digit
    if not any(ch.isalpha() for ch in text) or not any(ch.isdigit() for ch in text):
        return False

    # Prefer plates with a strongly letter-digit mix and realistic plate length.
    if re.fullmatch(r'[A-Z]{2,4}[0-9]{2,4}[A-Z0-9]{1,6}', text):
        return True

    if re.fullmatch(r'[A-Z]{1,3}[0-9]{1,4}[A-Z0-9]{2,8}', text):
        return True

    if re.fullmatch(r'[A-Z0-9]{4,15}', text):
        # Accept only if the token is not short OCR noise and contains a meaningful mix
        if text[0].isdigit():
            return False
        if sum(ch.isdigit() for ch in text) < 2:
            return False
        return True

    return False


def validate_indian_plate(text: str) -> bool:
    """Backward-compatible wrapper for Indian-specific validation."""
    if not text:
        return False

    text = text.strip().upper()
    if len(text) < 4 or len(text) > 15:
        return False

    if text.isdigit() or text.isalpha():
        return False

    if not any(ch.isalpha() for ch in text) or not any(ch.isdigit() for ch in text):
        return False

    if re.fullmatch(r'[A-Z]{2,4}[0-9]{2,4}[A-Z0-9]{1,6}', text):
        return True

    if re.fullmatch(r'[A-Z]{2}\d{2}[A-Z0-9]{1,4}\d{1,4}', text):
        return True

    if re.fullmatch(r'[A-Z]{2}\d{1,2}[A-Z0-9]{1,4}\d{1,4}', text):
        return True

    return False


def is_ocr_available() -> Tuple[bool, Optional[str]]:
    """Check if OCR engine is available."""
    reader = _load_reader()
    if reader is not None:
        return True, None
    return False, _reader_error
