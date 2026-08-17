import numpy as np
import pytest

from app.api import camera


class FakeCap:
    def __init__(self, frame):
        self.frame = frame
        self.read_count = 0

    def isOpened(self):
        return True

    def read(self):
        if self.read_count == 0:
            self.read_count += 1
            return True, self.frame
        return False, None

    def release(self):
        pass

    def set(self, *args, **kwargs):
        return True

    def get(self, *args, **kwargs):
        return 0


@pytest.mark.asyncio
async def test_scan_plates_falls_back_to_frame_level_plate_detection(monkeypatch):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    monkeypatch.setattr(camera.cv2, 'VideoCapture', lambda source: FakeCap(frame))
    monkeypatch.setattr(camera, 'detect_vehicles', lambda image: [])
    monkeypatch.setattr(camera, 'detect_plate', lambda image: {"plate_crop": image, "confidence": 0.95})
    monkeypatch.setattr(camera, 'read_plate', lambda image: {"normalized_text": "AB12CD1234", "confidence": 0.97, "status": "OK"})
    monkeypatch.setattr(camera, 'save_plate_record', lambda **kwargs: None)

    result = await camera.scan_plates(source='0', mode='LIVE_CAMERA')

    assert result['status'] == 'ok'
    assert result['count'] == 1
    assert result['plates'][0]['plate_number'] == 'AB12CD1234'
