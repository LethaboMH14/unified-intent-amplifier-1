"""
calibrate_gaze.py — 5-point gaze calibration.
Run this ONCE before using gaze control. Look at each dot when prompted,
press SPACE to capture, then close. Saves calibration to user_profile.db.

Usage:
    python calibrate_gaze.py
"""

import sys
import time
import threading
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

try:
    import cv2
    import mediapipe as mp
    _OK = True
except ImportError:
    _OK = False
    print("ERROR: mediapipe or cv2 not installed.")
    sys.exit(1)

from user_profile import init_db, save_setting, load_setting
from config import IRIS_LEFT_IDX, IRIS_RIGHT_IDX, EAR_LEFT_IDX, EAR_RIGHT_IDX

# ── Calibration points (fractions of screen) ────────────────────────────────
CALIB_POINTS = [
    (0.5,  0.5),   # centre
    (0.05, 0.05),  # top-left
    (0.95, 0.05),  # top-right
    (0.05, 0.95),  # bottom-left
    (0.95, 0.95),  # bottom-right
]
POINT_LABELS = ["Centre", "Top-Left", "Top-Right", "Bottom-Left", "Bottom-Right"]
SAMPLES_PER_POINT = 30


def _iris_ratios(lm, w, h):
    """Compute iris X/Y ratio within eye socket from landmarks."""
    lx = np.mean([lm[i].x * w for i in IRIS_LEFT_IDX])
    ly = np.mean([lm[i].y * h for i in IRIS_LEFT_IDX])
    rx = np.mean([lm[i].x * w for i in IRIS_RIGHT_IDX])
    ry = np.mean([lm[i].y * h for i in IRIS_RIGHT_IDX])

    l_inner = lm[133].x * w
    l_outer = lm[33].x * w
    r_inner = lm[362].x * w
    r_outer = lm[263].x * w

    ratio_x_l = (lx - l_outer) / (l_inner - l_outer + 1e-6)
    ratio_x_r = (rx - r_inner) / (r_outer - r_inner + 1e-6)
    ratio_x = (ratio_x_l + ratio_x_r) / 2.0

    l_top = lm[159].y * h
    l_bot = lm[145].y * h
    r_top = lm[386].y * h
    r_bot = lm[374].y * h
    ratio_y_l = (ly - l_top) / (l_bot - l_top + 1e-6)
    ratio_y_r = (ry - r_top) / (r_bot - r_top + 1e-6)
    ratio_y = (ratio_y_l + ratio_y_r) / 2.0

    return float(ratio_x), float(ratio_y)


class CalibrationApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#0d0d1f")

        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()

        self.canvas = tk.Canvas(self.root, bg="#0d0d1f", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.cap = cv2.VideoCapture(0)
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1, refine_landmarks=True,
            min_detection_confidence=0.5, min_tracking_confidence=0.5
        )

        self.point_idx = 0
        self.collecting = False
        self.samples = []
        self.calib_data = []  # list of (screen_x_ratio, screen_y_ratio, eye_x, eye_y)

        self.root.bind("<space>", self._on_space)
        self.root.bind("<Escape>", lambda e: self._finish())

        self._draw_point()

    def _draw_point(self):
        self.canvas.delete("all")
        if self.point_idx >= len(CALIB_POINTS):
            self._finish()
            return

        px, py = CALIB_POINTS[self.point_idx]
        sx = int(px * self.sw)
        sy = int(py * self.sh)
        label = POINT_LABELS[self.point_idx]

        # Instructions
        self.canvas.create_text(
            self.sw // 2, 40,
            text=f"Point {self.point_idx + 1}/{len(CALIB_POINTS)}: Look at the dot  →  {label}  →  Press SPACE to capture",
            fill="#00d4ff", font=("Segoe UI", 16), anchor="center"
        )
        self.canvas.create_text(
            self.sw // 2, 75,
            text="Press ESC when done with all points",
            fill="#666688", font=("Segoe UI", 11), anchor="center"
        )

        # Target dot
        r = 18
        self.canvas.create_oval(sx-r, sy-r, sx+r, sy+r, fill="#00d4ff", outline="white", width=2)
        self.canvas.create_oval(sx-5, sy-5, sx+5, sy+5, fill="white")

    def _on_space(self, event):
        if self.collecting:
            return
        self.collecting = True
        self.samples = []
        self.canvas.create_text(
            self.sw // 2, 110,
            text="Capturing... hold still",
            fill="#ffaa00", font=("Segoe UI", 13), anchor="center",
            tags="status"
        )
        threading.Thread(target=self._collect, daemon=True).start()

    def _collect(self):
        """Capture SAMPLES_PER_POINT eye ratio readings."""
        collected = []
        while len(collected) < SAMPLES_PER_POINT:
            ret, frame = self.cap.read()
            if not ret:
                continue
            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = self.face_mesh.process(rgb)
            if result.multi_face_landmarks:
                lm = result.multi_face_landmarks[0].landmark
                rx, ry = _iris_ratios(lm, w, h)
                collected.append((rx, ry))
            time.sleep(0.033)

        mean_x = float(np.median([s[0] for s in collected]))
        mean_y = float(np.median([s[1] for s in collected]))

        px, py = CALIB_POINTS[self.point_idx]
        self.calib_data.append((px, py, mean_x, mean_y))
        print(f"  Point {self.point_idx+1} ({POINT_LABELS[self.point_idx]}): "
              f"screen=({px:.2f},{py:.2f})  eye=({mean_x:.3f},{mean_y:.3f})")

        self.point_idx += 1
        self.collecting = False
        self.root.after(0, self._draw_point)

    def _finish(self):
        """Save calibration and close."""
        self.cap.release()
        if len(self.calib_data) >= 3:
            self._save_calibration()
            self.canvas.delete("all")
            self.canvas.create_text(
                self.sw // 2, self.sh // 2,
                text=f"✓ Calibration saved ({len(self.calib_data)} points)\n\nClose this window and run main.py",
                fill="#00d4ff", font=("Segoe UI", 20), anchor="center", justify="center"
            )
            self.root.after(3000, self.root.destroy)
        else:
            print("Not enough points captured — need at least 3. Run again.")
            self.root.destroy()

    def _save_calibration(self):
        """Compute and save eye-to-screen mapping parameters."""
        eye_xs = [d[2] for d in self.calib_data]
        eye_ys = [d[3] for d in self.calib_data]
        scr_xs = [d[0] for d in self.calib_data]
        scr_ys = [d[1] for d in self.calib_data]

        # Linear fit: screen = scale * eye + offset
        # x axis
        eye_x_range = max(eye_xs) - min(eye_xs) + 1e-6
        scr_x_range = max(scr_xs) - min(scr_xs)
        scale_x = scr_x_range / eye_x_range
        offset_x = np.mean(scr_xs) - scale_x * np.mean(eye_xs)

        # y axis
        eye_y_range = max(eye_ys) - min(eye_ys) + 1e-6
        scr_y_range = max(scr_ys) - min(scr_ys)
        scale_y = scr_y_range / eye_y_range
        offset_y = np.mean(scr_ys) - scale_y * np.mean(eye_ys)

        calib = {
            "scale_x": scale_x,
            "offset_x": offset_x,
            "scale_y": scale_y,
            "offset_y": offset_y,
            "eye_x_min": min(eye_xs),
            "eye_x_max": max(eye_xs),
            "eye_y_min": min(eye_ys),
            "eye_y_max": max(eye_ys),
        }
        init_db()
        save_setting("gaze_calibration", calib)
        print("\nCalibration saved:")
        for k, v in calib.items():
            print(f"  {k}: {v:.4f}")

    def run(self):
        self.root.mainloop()


def main():
    print("=" * 50)
    print("  Gaze Calibration — Unified Intent Amplifier")
    print("=" * 50)
    print("Instructions:")
    print("  1. Sit at your normal distance from the screen")
    print("  2. Look at each dot when it appears")
    print("  3. Press SPACE to capture that point")
    print("  4. Repeat for all 5 points")
    print("  5. Press ESC when done\n")
    app = CalibrationApp()
    app.run()


if __name__ == "__main__":
    main()
