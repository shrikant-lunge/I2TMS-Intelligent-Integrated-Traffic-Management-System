"""
Evidence Service - Captures and stores violation evidence images.
"""

import os
import logging
import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from app.config import EVIDENCE_DIR, PLATES_DIR

logger = logging.getLogger(__name__)


def save_evidence(
    violation_id: str,
    full_frame: np.ndarray,
    vehicle_crop: np.ndarray,
    plate_crop: Optional[np.ndarray],
    metadata: dict,
) -> str:
    """
    Save evidence images for a violation.

    Returns the evidence directory path (relative to project root).
    """
    # Create evidence directory
    evidence_dir = EVIDENCE_DIR / violation_id
    evidence_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Save full frame
        full_path = evidence_dir / "full_frame.jpg"
        cv2.imwrite(str(full_path), full_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])

        # Save vehicle crop
        vehicle_path = evidence_dir / "vehicle.jpg"
        if vehicle_crop is not None and vehicle_crop.size > 0:
            cv2.imwrite(str(vehicle_path), vehicle_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])

        # Save plate crop
        if plate_crop is not None and plate_crop.size > 0:
            plate_path = evidence_dir / "plate.jpg"
            cv2.imwrite(str(plate_path), plate_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])

            # Also save to plates directory for reference
            plates_copy = PLATES_DIR / f"{violation_id}_plate.jpg"
            cv2.imwrite(str(plates_copy), plate_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])

        # Save metadata
        meta_path = evidence_dir / "metadata.txt"
        with open(meta_path, "w") as f:
            f.write(f"Violation ID: {violation_id}\n")
            for key, value in metadata.items():
                f.write(f"{key}: {value}\n")
            f.write(f"Saved at: {datetime.datetime.utcnow().isoformat()}\n")

        logger.info(f"Evidence saved: {evidence_dir}")
        return str(evidence_dir)

    except Exception as e:
        logger.error(f"Failed to save evidence: {e}")
        return str(evidence_dir)


def get_evidence_path(violation_id: str) -> Optional[Path]:
    """Get the evidence directory for a violation."""
    evidence_dir = EVIDENCE_DIR / violation_id
    if evidence_dir.exists():
        return evidence_dir
    return None


def get_evidence_images(violation_id: str) -> dict:
    """Get paths to evidence images."""
    evidence_dir = EVIDENCE_DIR / violation_id
    result = {
        "full_frame": None,
        "vehicle": None,
        "plate": None,
    }

    if not evidence_dir.exists():
        return result

    for name in ["full_frame.jpg", "vehicle.jpg", "plate.jpg"]:
        path = evidence_dir / name
        if path.exists():
            key = name.replace(".jpg", "")
            result[key] = str(path)

    return result
