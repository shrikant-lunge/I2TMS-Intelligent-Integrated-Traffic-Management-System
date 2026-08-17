"""Uploaded-video ANPR runner based exclusively on the supplied ANPR project.

This path deliberately does not use TMS detection_service, plate_service,
ocr_service, tracking_service, or the emergency pipeline.  It follows the
provided project's model + SORT + OCR flow and writes an annotated video.
"""

from __future__ import annotations

import csv
import logging
import threading
from pathlib import Path

import cv2
import numpy as np

from app.config import BACKEND_ROOT, VIDEOS_DIR

logger = logging.getLogger(__name__)

ANPR_ROOT = BACKEND_ROOT / "anpr_demo"
COCO_MODEL_PATH = ANPR_ROOT / "yolov8n.pt"
PLATE_MODEL_PATH = ANPR_ROOT / "models" / "license_plate_detector.pt"
OUTPUT_DIR = VIDEOS_DIR / "anpr_output"

_run_lock = threading.Lock()


def _get_anpr_components():
    """Import the original ANPR project's models, SORT tracker and OCR helper."""
    if not COCO_MODEL_PATH.is_file() or not PLATE_MODEL_PATH.is_file():
        raise RuntimeError("Supplied ANPR model files are missing from backend/anpr_demo")

    from ultralytics import YOLO
    # These are the preserved modules extracted from the supplied archive.
    from anpr_demo.sort.sort import Sort
    from anpr_demo.util import get_car, read_license_plate

    return YOLO, Sort, get_car, read_license_plate


def process_uploaded_video(source: Path) -> dict:
    """Run the supplied ANPR workflow and produce a playable annotated MP4 + CSV."""
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Uploaded video not found: {source.name}")

    with _run_lock:
        YOLO, Sort, get_car, read_license_plate = _get_anpr_components()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_stem = f"anpr_{source.stem}"
        annotated_path = OUTPUT_DIR / f"{output_stem}.mp4"
        csv_path = OUTPUT_DIR / f"{output_stem}.csv"

        cap = cv2.VideoCapture(str(source))
        if not cap.isOpened():
            raise RuntimeError("Unable to open uploaded video")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter(
            str(annotated_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
        )
        if not writer.isOpened():
            cap.release()
            raise RuntimeError("Unable to create annotated ANPR video")

        # Exact supplied model roles: COCO vehicle detector, dedicated licence
        # plate detector, SORT vehicle tracker, and supplied strict OCR reader.
        coco_model = YOLO(str(COCO_MODEL_PATH))
        plate_model = YOLO(str(PLATE_MODEL_PATH))
        mot_tracker = Sort()
        vehicles = [2, 3, 5, 7]
        best_by_car: dict[int, tuple[str, float]] = {}
        rows: list[dict] = []
        frame_number = 0

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break

                detections = coco_model(frame, verbose=False)[0]
                vehicle_detections = [
                    [x1, y1, x2, y2, score]
                    for x1, y1, x2, y2, score, class_id in detections.boxes.data.tolist()
                    if int(class_id) in vehicles
                ]
                tracks = mot_tracker.update(
                    np.asarray(vehicle_detections) if vehicle_detections else np.empty((0, 5))
                )

                # Same stable car labels used by the supplied main.py.
                for x1, y1, x2, y2, car_id in tracks:
                    car_id = int(car_id)
                    p1, p2 = (int(x1), int(y1)), (int(x2), int(y2))
                    cv2.rectangle(frame, p1, p2, (0, 200, 0), 2)
                    label = best_by_car.get(car_id)
                    if label:
                        cv2.putText(frame, label[0], (p1[0], max(p1[1] - 10, 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)

                plates = plate_model(frame, verbose=False)[0]
                for x1, y1, x2, y2, score, class_id in plates.boxes.data.tolist():
                    xcar1, ycar1, xcar2, ycar2, car_id = get_car(
                        [x1, y1, x2, y2, score, class_id], tracks
                    )
                    if car_id == -1:
                        continue

                    crop = frame[max(0, int(y1)):max(0, int(y2)), max(0, int(x1)):max(0, int(x2))]
                    if crop.size == 0:
                        continue
                    crop_h, crop_w = crop.shape[:2]
                    if crop_h < 60:
                        scale = 60 / crop_h
                        crop = cv2.resize(crop, (int(crop_w * scale), 60), interpolation=cv2.INTER_CUBIC)
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    _, thresholded = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                    text, text_score = read_license_plate(thresholded)
                    if text is None:
                        continue

                    car_id = int(car_id)
                    if car_id not in best_by_car or text_score > best_by_car[car_id][1]:
                        best_by_car[car_id] = (text, float(text_score))
                    p1, p2 = (int(x1), int(y1)), (int(x2), int(y2))
                    cv2.rectangle(frame, p1, p2, (0, 0, 255), 2)
                    cv2.putText(frame, f"PLATE: {text}", (p1[0], max(p1[1] - 10, 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
                    rows.append({"frame_number": frame_number, "car_id": car_id, "plate_number": text, "confidence": round(float(text_score), 3)})

                cv2.putText(frame, "ANPR MODEL: license_plate_detector.pt", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)
                writer.write(frame)
                frame_number += 1
        finally:
            cap.release()
            writer.release()

        unique_plates = {}
        for row in rows:
            if row["plate_number"] not in unique_plates or row["confidence"] > unique_plates[row["plate_number"]]["confidence"]:
                unique_plates[row["plate_number"]] = row
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer_csv = csv.DictWriter(csv_file, fieldnames=["frame_number", "car_id", "plate_number", "confidence"])
            writer_csv.writeheader()
            writer_csv.writerows(unique_plates.values())

        return {
            "video_filename": annotated_path.name,
            "plates": list(unique_plates.values()),
            "count": len(unique_plates),
            "frames_processed": frame_number,
            "model": str(PLATE_MODEL_PATH),
        }
