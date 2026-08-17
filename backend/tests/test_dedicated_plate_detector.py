"""Unit tests for integration of the supplied YOLOv8 ANPR detector."""

import numpy as np

from app.services import plate_service


class _Box:
    def __init__(self, bbox, confidence):
        self.xyxy = [np.array(bbox, dtype=float)]
        self.conf = [confidence]


class _Result:
    def __init__(self, boxes):
        self.boxes = boxes


class _Model:
    def __call__(self, image, **kwargs):
        return [_Result([_Box([10, 8, 50, 22], 0.91)])]


def test_dedicated_detector_returns_relative_crop(monkeypatch):
    image = np.zeros((60, 100, 3), dtype=np.uint8)
    monkeypatch.setattr(plate_service, "_load_plate_model", lambda: _Model())

    result = plate_service._detect_plate_with_yolo(image)

    assert result["detector"] == "yolov8_anpr"
    assert result["confidence"] == 0.91
    assert result["plate_bbox"] == [7, 5, 53, 25]
    assert result["plate_crop"].shape == (20, 46, 3)


def test_contour_detector_remains_available_when_model_has_no_result(monkeypatch):
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    monkeypatch.setattr(plate_service, "_detect_plate_with_yolo", lambda _: None)
    monkeypatch.setattr(plate_service, "_morphological_plate_detection", lambda *_: {
        "plate_bbox": [2, 2, 20, 10],
        "plate_crop": image[2:10, 2:20],
        "confidence": 0.3,
        "detector": "morphology",
    })

    result = plate_service.detect_plate(image)

    assert result["detector"] == "morphology"
