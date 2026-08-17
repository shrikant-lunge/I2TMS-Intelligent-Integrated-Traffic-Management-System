"""
Generate a synthetic demo traffic video for testing.
Creates a video with simulated vehicle movements.

Usage:
    python scripts/generate_demo_video.py
"""

import sys
import os
import random
import math

# Check OpenCV availability
try:
    import cv2
    import numpy as np
except ImportError:
    print("OpenCV not available yet. Install with: pip install opencv-python-headless numpy")
    sys.exit(1)

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIDEOS_DIR = PROJECT_ROOT / "data" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = VIDEOS_DIR / "demo_traffic.mp4"


class SimulatedVehicle:
    """A vehicle moving through the simulated scene."""

    def __init__(self, frame_w, frame_h):
        self.w = frame_w
        self.h = frame_h
        # Spawn at top center area, move downward (toward camera)
        self.x = random.randint(frame_w // 4, 3 * frame_w // 4)
        self.y = random.randint(0, frame_h // 4)
        self.speed_y = random.uniform(1.0, 3.5)
        self.speed_x = random.uniform(-0.5, 0.5)
        self.vtype = random.choice(["car", "truck", "bus", "motorcycle"])
        self.color = self._get_color()
        self.size = self._get_size()
        self.plate = self._gen_plate()
        self.active = True
        # Some vehicles will "stop" (block the corridor)
        self.will_stop = random.random() < 0.25
        self.stop_y = random.randint(frame_h // 3, 2 * frame_h // 3)
        self.stopped = False
        self.stop_timer = 0

    def _get_color(self):
        colors = {
            "car": [(200, 200, 220), (30, 30, 200), (200, 30, 30), (30, 180, 30), (180, 180, 30)],
            "truck": [(100, 100, 130), (50, 50, 180)],
            "bus": [(30, 30, 200), (200, 180, 30)],
            "motorcycle": [(60, 60, 60), (150, 30, 30)],
        }
        return random.choice(colors.get(self.vtype, [(128, 128, 128)]))

    def _get_size(self):
        sizes = {
            "car": (50, 70),
            "truck": (60, 100),
            "bus": (55, 110),
            "motorcycle": (25, 40),
        }
        return sizes.get(self.vtype, (50, 70))

    def _gen_plate(self):
        states = ["MH", "KA", "DL", "TN", "GJ", "RJ"]
        st = random.choice(states)
        dist = random.randint(1, 50)
        series = chr(random.randint(65, 90)) + chr(random.randint(65, 90))
        num = random.randint(1000, 9999)
        return f"{st}{dist:02d}{series}{num}"

    def update(self):
        if not self.active:
            return

        if self.will_stop and self.y >= self.stop_y and not self.stopped:
            self.stopped = True
            self.stop_timer = 0

        if self.stopped:
            self.stop_timer += 1
            # Stop for 120-200 frames then resume
            if self.stop_timer > random.randint(120, 200):
                self.stopped = False
                self.will_stop = False
            else:
                # Slight vibration while stopped
                self.x += random.uniform(-0.3, 0.3)
                return

        self.x += self.speed_x
        self.y += self.speed_y

        # Scale up as getting closer
        scale = 1.0 + (self.y / self.h) * 0.8

        if self.y > self.h + 50:
            self.active = False

    def draw(self, frame):
        if not self.active:
            return

        h, w = frame.shape[:2]
        # Perspective scaling
        scale = 0.6 + (self.y / h) * 1.0
        vw = int(self.size[0] * scale)
        vh = int(self.size[1] * scale)

        x1 = int(self.x - vw // 2)
        y1 = int(self.y - vh // 2)
        x2 = x1 + vw
        y2 = y1 + vh

        # Clip to frame
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return

        # Draw vehicle body
        cv2.rectangle(frame, (x1, y1), (x2, y2), self.color, -1)

        # Roof/outline
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 0), 1)

        # Windshield
        if vh > 30:
            ws_y1 = y1 + 3
            ws_y2 = y1 + int(vh * 0.25)
            ws_x1 = x1 + 3
            ws_x2 = x2 - 3
            if ws_y2 > ws_y1 and ws_x2 > ws_x1:
                cv2.rectangle(frame, (ws_x1, ws_y1), (ws_x2, ws_y2), (180, 200, 220), -1)

        # Number plate area (bottom of vehicle)
        if vh > 20 and vw > 20:
            pw = min(vw - 6, int(vw * 0.7))
            ph = max(8, int(vh * 0.12))
            px1 = x1 + (vw - pw) // 2
            py1 = y2 - ph - 3
            px2 = px1 + pw
            py2 = py1 + ph

            if py1 > y1 and px2 <= x2 and py2 <= y2:
                # White plate background
                cv2.rectangle(frame, (px1, py1), (px2, py2), (255, 255, 255), -1)
                cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 0, 0), 1)

                # Plate text
                font_scale = max(0.25, min(0.4, pw / 120))
                text = self.plate[:6]  # Abbreviated
                cv2.putText(frame, text, (px1 + 2, py2 - 2),
                           cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), 1)

        # Vehicle type label (small, for debugging)
        if self.stopped:
            cv2.putText(frame, "STOPPED", (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)


def generate_video():
    """Generate a synthetic traffic demo video."""
    W, H = 640, 480
    FPS = 25
    DURATION = 45  # seconds
    TOTAL_FRAMES = FPS * DURATION

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(str(OUTPUT_FILE), fourcc, FPS, (W, H))

    if not writer.isOpened():
        print("ERROR: Could not open video writer. Trying XVID...")
        output_avi = VIDEOS_DIR / "demo_traffic.avi"
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        writer = cv2.VideoWriter(str(output_avi), fourcc, FPS, (W, H))
        if not writer.isOpened():
            print("ERROR: Cannot create video. Check OpenCV codecs.")
            return False

    vehicles = []

    for frame_idx in range(TOTAL_FRAMES):
        # Road background
        frame = np.zeros((H, W, 3), dtype=np.uint8)

        # Sky gradient
        for y in range(H // 3):
            t = y / (H // 3)
            b = int(140 + 60 * t)
            g = int(160 + 40 * t)
            r = int(100 + 30 * t)
            frame[y, :] = (b, g, r)

        # Road
        road_top = H // 3
        road_color = (60, 60, 60)
        frame[road_top:, :] = road_color

        # Road lines (perspective)
        cx = W // 2
        for lane_offset in [-100, 0, 100]:
            top_x = cx + int(lane_offset * 0.4)
            bottom_x = cx + lane_offset
            for seg in range(5):
                seg_top = road_top + seg * (H - road_top) // 5
                seg_bot = seg_top + (H - road_top) // 10
                t_top = (seg_top - road_top) / (H - road_top)
                t_bot = (seg_bot - road_top) / (H - road_top)
                x_t = int(cx + lane_offset * (0.4 + 0.6 * t_top))
                x_b = int(cx + lane_offset * (0.4 + 0.6 * t_bot))
                # Animated dash
                if (frame_idx // 3 + seg) % 2 == 0:
                    cv2.line(frame, (x_t, seg_top), (x_b, seg_bot), (200, 200, 200), 1)

        # Road edges
        cv2.line(frame, (cx - int(W * 0.15), road_top), (0, H), (200, 200, 200), 2)
        cv2.line(frame, (cx + int(W * 0.15), road_top), (W, H), (200, 200, 200), 2)

        # Spawn new vehicles
        if frame_idx % random.randint(15, 35) == 0 and len([v for v in vehicles if v.active]) < 8:
            vehicles.append(SimulatedVehicle(W, H))

        # Update and draw vehicles
        for v in vehicles:
            v.update()
            v.draw(frame)

        # Clean up inactive vehicles
        vehicles = [v for v in vehicles if v.active]

        writer.write(frame)

        if frame_idx % 100 == 0:
            print(f"\rGenerating: {frame_idx}/{TOTAL_FRAMES} frames ({100*frame_idx//TOTAL_FRAMES}%)", end="", flush=True)

    writer.release()
    print(f"\nDemo video saved: {OUTPUT_FILE}")
    print(f"Duration: {DURATION}s, FPS: {FPS}, Resolution: {W}x{H}")
    return True


if __name__ == "__main__":
    success = generate_video()
    sys.exit(0 if success else 1)
