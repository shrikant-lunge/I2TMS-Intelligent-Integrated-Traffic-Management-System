"""
Camera Service - Manages camera/video input lifecycle.
Supports webcam, IP camera, and pre-recorded video.
"""

import cv2
import time
import logging
import threading
from typing import Optional

import numpy as np

from app.config import CAMERA_SOURCE, VIDEOS_DIR

logger = logging.getLogger(__name__)


class CameraService:
    """Manages video capture from various sources."""

    def __init__(self):
        self._lock = threading.Lock()
        self._cap: Optional[cv2.VideoCapture] = None
        self._running: bool = False
        self._mode: str = "UNAVAILABLE"
        self._source = CAMERA_SOURCE
        self._frame_count: int = 0
        self._fps: float = 0.0
        self._last_fps_time: float = 0.0
        self._fps_frame_count: int = 0
        self._current_frame: Optional[np.ndarray] = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def source(self) -> str:
        return str(self._source)

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def current_frame(self) -> Optional[np.ndarray]:
        return self._current_frame

    def start(self, source=None) -> bool:
        """Start video capture."""
        with self._lock:
            if self._running:
                self.stop()

            src = source if source is not None else self._source

            # If the caller explicitly provides a video path, use it.
            if isinstance(src, str) and src.strip() and not src.startswith(("http://", "rtsp://")) and not src.isdigit():
                if src.lower().endswith((".mp4", ".avi", ".mkv", ".mov", ".webm")):
                    self._cap = cv2.VideoCapture(src)
                    if self._cap.isOpened():
                        self._mode = "VIDEO FILE"
                        self._running = True
                        self._source = src
                        logger.info(f"Camera started: video file {src}")
                        return True
                    logger.warning(f"Video file not available: {src}")

            # Live camera sources should always be preferred over demo videos.
            try:
                if isinstance(src, int):
                    self._cap = cv2.VideoCapture(src)
                    if self._cap.isOpened():
                        self._mode = "LIVE CAMERA"
                        self._running = True
                        self._source = str(src)
                        logger.info(f"Camera started: webcam {src}")
                        return True
                    logger.warning(f"Webcam {src} not available")

                elif isinstance(src, str) and src.startswith(("http://", "rtsp://")):
                    self._cap = cv2.VideoCapture(src)
                    if self._cap.isOpened():
                        self._mode = "LIVE CAMERA"
                        self._running = True
                        self._source = src
                        logger.info(f"Camera started: IP camera {src}")
                        return True
                    logger.warning(f"IP camera not available: {src}")

                elif isinstance(src, str) and src == "0":
                    self._cap = cv2.VideoCapture(0)
                    if self._cap.isOpened():
                        self._mode = "LIVE CAMERA"
                        self._running = True
                        self._source = "0"
                        logger.info("Camera started: webcam 0")
                        return True
                    logger.warning("Webcam 0 not available")

                elif isinstance(src, str):
                    self._cap = cv2.VideoCapture(src)
                    if self._cap.isOpened():
                        self._mode = "VIDEO FILE"
                        self._running = True
                        self._source = src
                        logger.info(f"Camera started: video file {src}")
                        return True
                    logger.warning(f"Video file not available: {src}")

            except Exception as e:
                logger.error(f"Camera start error: {e}")

            # Never fallback to demo video when the user is in emergency mode.
            # Use live camera only. If no live camera is available, return False.
            logger.warning("No live camera available for emergency mode. Camera not started.")
            self._mode = "UNAVAILABLE"
            return False

    def _try_demo_videos(self) -> bool:
        """Try to open any demo video in the videos directory."""
        if not VIDEOS_DIR.exists():
            logger.warning("No videos directory found")
            self._mode = "UNAVAILABLE"
            return False

        for ext in ["*.mp4", "*.avi", "*.mkv", "*.mov", "*.webm"]:
            for video_file in VIDEOS_DIR.glob(ext):
                try:
                    self._cap = cv2.VideoCapture(str(video_file))
                    if self._cap.isOpened():
                        self._mode = "DEMO VIDEO"
                        self._running = True
                        self._source = str(video_file)
                        logger.info(f"Demo video loaded: {video_file}")
                        return True
                except Exception:
                    continue

        logger.warning("No demo video available. Camera mode: UNAVAILABLE")
        self._mode = "UNAVAILABLE"
        return False

    def read_frame(self) -> Optional[np.ndarray]:
        """Read a single frame from the video source."""
        if not self._running or self._cap is None:
            return None

        try:
            ret, frame = self._cap.read()

            if not ret:
                # Uploaded and demo files loop so the dashboard remains a
                # continuous playable ANPR feed after the first pass.
                if self._mode in {"DEMO VIDEO", "VIDEO FILE"}:
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = self._cap.read()
                    if not ret:
                        return None
                    logger.info("Video looped")
                else:
                    return None

            self._frame_count += 1
            self._current_frame = frame

            # Calculate FPS
            now = time.time()
            self._fps_frame_count += 1
            elapsed = now - self._last_fps_time
            if elapsed >= 1.0:
                self._fps = round(self._fps_frame_count / elapsed, 1)
                self._fps_frame_count = 0
                self._last_fps_time = now

            return frame

        except Exception as e:
            logger.error(f"Frame read error: {e}")
            return None

    def stop(self):
        """Stop video capture."""
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            self._running = False
            self._current_frame = None
            self._frame_count = 0
            self._fps = 0.0
            logger.info("Camera stopped")

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "mode": self._mode,
            "source": str(self._source),
            "frame_count": self._frame_count,
            "fps": self._fps,
        }


# Singleton
camera_service = CameraService()
