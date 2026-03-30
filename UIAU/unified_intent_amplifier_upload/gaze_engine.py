"""
gaze_engine.py — Head-compensated iris gaze tracking.

FIXES APPLIED:
  - FIX 1: Iris landmark swap auto-detection on first frame
            MediaPipe labels LEFT iris from camera perspective = user's RIGHT
            If indices are swapped, gaze goes opposite direction — auto-corrects
  - FIX 2: App Insights telemetry on blink clicks and gaze accuracy
  - FIX 3: Blink click confirmation — 2-second delay on form submit buttons
  - FIX 4: atexit guard for clean webcam release
  - FIX 5: GAZE_DEBUG set to False for production (was True — spamming terminal)
"""

import threading
import time
import logging
import atexit
import os
from collections import deque
import numpy as np
import pyautogui
from config import (
    GAZE_SMOOTHING_ALPHA, GAZE_BLINK_EAR_THRESHOLD, GAZE_BLINK_FRAMES,
    GAZE_DWELL_MS, GAZE_DEAD_ZONE_PX, THREAD_SLEEP_MS,
    IRIS_LEFT_IDX, IRIS_RIGHT_IDX, EAR_LEFT_IDX, EAR_RIGHT_IDX,
)

logger = logging.getLogger(__name__)
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

try:
    import cv2
    import mediapipe as mp
    _MP_OK = True
except ImportError:
    _MP_OK = False
    logger.warning("mediapipe/cv2 not installed — gaze disabled")

# ── Application Insights ────────────────────────────────────────────────────
_tc = None
if os.getenv("USE_APP_INSIGHTS", "false").lower() == "true":
    try:
        from applicationinsights import TelemetryClient
        _tc = TelemetryClient(os.getenv("AZURE_APPINSIGHTS_INSTRUMENTATION_KEY", ""))
    except ImportError:
        pass

def _track(event: str, props: dict = None):
    if _tc:
        try:
            _tc.track_event(event, props or {})
        except Exception:
            pass

# FIX 5: Debug off for production — was True, spamming terminal every 30 frames
GAZE_DEBUG = False


def _ear(lm, indices, w, h):
    pts = np.array([[lm[i].x * w, lm[i].y * h] for i in indices])
    v1 = np.linalg.norm(pts[1] - pts[5])
    v2 = np.linalg.norm(pts[2] - pts[4])
    h1 = np.linalg.norm(pts[0] - pts[3])
    return (v1 + v2) / (2.0 * h1 + 1e-6)


class RangeTracker:
    """
    Tracks the min/max of a value stream with fast expansion and slow contraction.
    Gives a stable personal range without needing explicit calibration.
    """
    def __init__(self, init_lo=0.45, init_hi=0.55, contraction=0.0004):
        self.lo = init_lo
        self.hi = init_hi
        self.contraction = contraction
        self.n = 0

    def update(self, v):
        if v < self.lo:
            self.lo = v
        else:
            self.lo += self.contraction
        if v > self.hi:
            self.hi = v
        else:
            self.hi -= self.contraction
        if self.hi - self.lo < 0.08:
            # Keep a minimum range so normalisation doesn't collapse
            mid = (self.hi + self.lo) / 2
            self.lo = mid - 0.04
            self.hi = mid + 0.04
        self.n += 1

    def normalise(self, v):
        return float(np.clip((v - self.lo) / (self.hi - self.lo), 0.0, 1.0))

    @property
    def ready(self):
        return self.n >= 20


class Kalman1D:
    def __init__(self, q=0.005, r=3.0):
        self.q = q
        self.r = r
        self.x = 0.5
        self.p = 1.0
        self._initialized = False

    def update(self, z):
        if not self._initialized:
            self.x = z
            self._initialized = True
            return z
        self.p += self.q
        k = self.p / (self.p + self.r)
        self.x += k * (z - self.x)
        self.p *= (1 - k)
        return self.x


class GazeEngine:
    def __init__(self):
        self.enabled = False
        self._running = False
        self._thread = None
        self._cap = None  # Keep reference for atexit cleanup

        # Wider initial range allows gaze to reach screen corners
        # X: horizontal iris movement has good range
        # Y: vertical is naturally compressed - start even wider
        self._rx = RangeTracker(0.35, 0.65)
        self._ry = RangeTracker(0.30, 0.70)
        self._kx = Kalman1D(q=0.008, r=4.0)
        self._ky = Kalman1D(q=0.008, r=4.0)

        self._smooth_x = 960.0
        self._smooth_y = 540.0
        self._blink_counter = 0
        self._last_click_ms = 0.0
        self._frame = 0
        self._blink_count_total = 0

        # FIX 1: Iris swap detection state
        self._iris_swap_checked = False
        self._iris_left_idx = list(IRIS_LEFT_IDX)
        self._iris_right_idx = list(IRIS_RIGHT_IDX)

        # FIX 3: Click confirmation state
        self._pending_click = False
        self._pending_click_deadline = 0.0
        self.on_confirm_callback = None  # overlay shows "Confirm click? Blink again"

        # Snap dwell state
        self._snap_dwell_counter = 0
        self._snap_candidate = None

        atexit.register(self._cleanup)

    def _cleanup(self):
        """FIX 4: Guaranteed webcam release on exit."""
        self._running = False
        if self._cap and self._cap.isOpened():
            self._cap.release()
            logger.info("GazeEngine: webcam released")

    def _check_iris_swap(self, lm, w: int) -> None:
        """
        FIX 1: Auto-detect if iris landmark indices are swapped.

        MediaPipe FaceMesh labels landmarks from the CAMERA's perspective.
        LEFT iris (474-477) = left side of the camera image = user's RIGHT eye.
        RIGHT iris (469-472) = right side of the camera image = user's LEFT eye.

        After cv2.flip(frame, 1) the image is mirrored, so:
        - IRIS_LEFT_IDX should produce a SMALLER x value (left side of screen)
        - IRIS_RIGHT_IDX should produce a LARGER x value (right side of screen)

        If this is reversed, gaze goes in the wrong direction — auto-swap fixes it.
        Only runs once on the first valid frame.
        """
        if self._iris_swap_checked:
            return

        left_x = np.mean([lm[i].x * w for i in self._iris_left_idx])
        right_x = np.mean([lm[i].x * w for i in self._iris_right_idx])

        # After flip, left iris should be at smaller x than right iris
        if left_x > right_x:
            self._iris_left_idx, self._iris_right_idx = (
                self._iris_right_idx, self._iris_left_idx
            )
            logger.warning(
                "FIX 1: Iris indices were SWAPPED (left_x=%.1f > right_x=%.1f) — "
                "auto-corrected. Gaze direction is now correct.", left_x, right_x
            )
            _track("IrisSwapDetectedAndFixed", {
                "left_x": f"{left_x:.1f}",
                "right_x": f"{right_x:.1f}"
            })
        else:
            logger.info(
                "FIX 1: Iris indices verified correct "
                "(left_x=%.1f < right_x=%.1f)", left_x, right_x
            )
            _track("IrisIndicesVerified")

        self._iris_swap_checked = True

    def _iris_ratio(self, lm, w, h):
        """
        Compute iris position as a ratio within the eye socket.
        Uses self._iris_left_idx / self._iris_right_idx which may have been
        auto-corrected by _check_iris_swap().
        """
        lx = np.mean([lm[i].x * w for i in self._iris_left_idx])
        ly = np.mean([lm[i].y * h for i in self._iris_left_idx])
        rx = np.mean([lm[i].x * w for i in self._iris_right_idx])
        ry = np.mean([lm[i].y * h for i in self._iris_right_idx])

        # Eye corners (horizontal reference)
        l_left  = lm[33].x * w
        l_right = lm[133].x * w
        r_left  = lm[362].x * w
        r_right = lm[263].x * w

        # Eye top/bottom (vertical reference)
        l_top = lm[159].y * h
        l_bot = lm[145].y * h
        r_top = lm[386].y * h
        r_bot = lm[374].y * h

        rx_l = (lx - l_left)  / (l_right - l_left  + 1e-6)
        rx_r = (rx - r_left)  / (r_right - r_left  + 1e-6)
        ratio_x = (rx_l + rx_r) / 2.0

        ry_l = (ly - l_top) / (l_bot - l_top + 1e-6)
        ry_r = (ry - r_top) / (r_bot - r_top + 1e-6)
        ratio_y = (ry_l + ry_r) / 2.0

        return float(ratio_x), float(ratio_y)

    def _handle_blink_click(self) -> None:
        """
        FIX 3: Two-blink confirmation for clicks near form submit/apply buttons.
        First blink near a submit button → show confirmation prompt.
        Second blink within 2 seconds → confirms and clicks.
        Single blink on normal areas → clicks immediately as before.
        """
        now_ms = time.time() * 1000

        # Check if we're in a pending confirmation window
        if self._pending_click:
            if now_ms < self._pending_click_deadline:
                # Second blink confirms
                pyautogui.click(_pause=False)
                self._blink_count_total += 1
                self._last_click_ms = now_ms
                self._pending_click = False
                logger.info("Gaze CONFIRMED click at (%d,%d)",
                            int(self._smooth_x), int(self._smooth_y))
                _track("GazeClickConfirmed", {
                    "x": str(int(self._smooth_x)),
                    "y": str(int(self._smooth_y))
                })
                if self.on_confirm_callback:
                    self.on_confirm_callback(False)  # Hide confirmation prompt
                return
            else:
                # Confirmation expired
                self._pending_click = False
                if self.on_confirm_callback:
                    self.on_confirm_callback(False)

        if now_ms - self._last_click_ms < GAZE_DWELL_MS:
            return

        # Check if cursor is near a sensitive area (bottom of screen = submit buttons)
        sw, sh = pyautogui.size()
        near_submit = self._smooth_y > sh * 0.8  # Bottom 20% of screen

        if near_submit:
            # Start confirmation window — require second blink within 2 seconds
            self._pending_click = True
            self._pending_click_deadline = now_ms + 2000
            logger.info("Gaze click PENDING confirmation at (%d,%d) — blink again to confirm",
                        int(self._smooth_x), int(self._smooth_y))
            _track("GazeClickPendingConfirmation")
            if self.on_confirm_callback:
                self.on_confirm_callback(True)  # Show "Blink again to confirm"
        else:
            # Normal click — immediate
            pyautogui.click(_pause=False)
            self._blink_count_total += 1
            self._last_click_ms = now_ms
            logger.info("Gaze click at (%d,%d)", int(self._smooth_x), int(self._smooth_y))
            _track("GazeClickImmediate", {
                "x": str(int(self._smooth_x)),
                "y": str(int(self._smooth_y)),
                "total_clicks": str(self._blink_count_total)
            })

    def _run(self):
        if not _MP_OK:
            logger.warning("GazeEngine: mediapipe unavailable")
            return

        self._cap = cv2.VideoCapture(0)
        if not self._cap.isOpened():
            logger.warning("GazeEngine: no webcam found — gaze disabled")
            _track("GazeEngineNoWebcam")
            return

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        sw, sh = pyautogui.size()
        self._smooth_x = sw / 2.0
        self._smooth_y = sh / 2.0
        logger.info("GazeEngine started (screen %dx%d)", sw, sh)
        _track("GazeEngineStarted", {"screen_w": str(sw), "screen_h": str(sh)})

        try:
            while self._running:
                if not self.enabled:
                    time.sleep(THREAD_SLEEP_MS / 1000)
                    continue

                ret, frame = self._cap.read()
                if not ret:
                    time.sleep(THREAD_SLEEP_MS / 1000)
                    continue

                frame = cv2.flip(frame, 1)
                h, w = frame.shape[:2]
                results = face_mesh.process(
                    cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

                if not results.multi_face_landmarks:
                    time.sleep(THREAD_SLEEP_MS / 1000)
                    continue

                lm = results.multi_face_landmarks[0].landmark
                self._frame += 1

                # FIX 1: Check and auto-correct iris swap on first valid frame
                self._check_iris_swap(lm, w)

                # ── Raw iris ratios ────────────────────────────────────────
                raw_x, raw_y = self._iris_ratio(lm, w, h)

                # ── Update personal range ──────────────────────────────────
                self._rx.update(raw_x)
                self._ry.update(raw_y)

                if not self._rx.ready:
                    time.sleep(THREAD_SLEEP_MS / 1000)
                    continue

                # ── Normalise → Kalman → screen ────────────────────────────
                norm_x = self._rx.normalise(raw_x)
                norm_y = self._ry.normalise(raw_y)

                # Nonlinear expansion — push gaze toward edges
                # Without this, gaze clusters in centre and corners are unreachable
                # Power < 1 compresses centre, stretches edges
                import numpy as _np2
                def _expand(v, power=0.75):
                    # Map [0,1] → [0,1] with edge expansion
                    return float(_np2.sign(v - 0.5) * abs(v - 0.5) ** power
                                 * (0.5 ** (1 - power)) + 0.5)

                norm_x = float(_np2.clip(_expand(norm_x, 0.78), 0.0, 1.0))
                norm_y = float(_np2.clip(_expand(norm_y, 0.72), 0.0, 1.0))

                filt_x = self._kx.update(norm_x)
                filt_y = self._ky.update(norm_y)
                target_x = float(np.clip(filt_x * sw, 0, sw - 1))
                target_y = float(np.clip(filt_y * sh, 0, sh - 1))

                # ── Adaptive EMA smoothing ───────────────────────────────────
                # Slow smoothing near edges (within 100px) for precision targeting
                sw, sh = pyautogui.size()
                edge_x = min(target_x, sw - target_x) < 100
                edge_y = min(target_y, sh - target_y) < 100
                a = GAZE_SMOOTHING_ALPHA * 0.6 if (edge_x or edge_y) else GAZE_SMOOTHING_ALPHA
                new_x = a * target_x + (1 - a) * self._smooth_x
                new_y = a * target_y + (1 - a) * self._smooth_y

                # ── Magnetic snap with dwell confirmation ──────────────────
                try:
                    from ui_automation import ui_automation as _uia
                    snapped_x, snapped_y = _uia.check_snap(new_x, new_y)
                    snapped = (snapped_x != new_x or snapped_y != new_y)
                    if snapped:
                        self._snap_dwell_counter += 1
                        self._snap_candidate = (snapped_x, snapped_y)
                    else:
                        self._snap_dwell_counter = 0
                        self._snap_candidate = None
                    # Only apply snap after dwelling near the button
                    from config import GAZE_SNAP_DWELL_FRAMES
                    if snapped and self._snap_dwell_counter >= GAZE_SNAP_DWELL_FRAMES:
                        new_x, new_y = snapped_x, snapped_y
                    # else: continue with unsnapped gaze
                except Exception:
                    pass

                # ── Dead zone ──────────────────────────────────────────────
                if (abs(new_x - self._smooth_x) > GAZE_DEAD_ZONE_PX or
                        abs(new_y - self._smooth_y) > GAZE_DEAD_ZONE_PX):
                    self._smooth_x = new_x
                    self._smooth_y = new_y
                    pyautogui.moveTo(int(self._smooth_x), int(self._smooth_y),
                                     _pause=False)

                # ── Debug output every 30 frames (off by default) ──────────
                if GAZE_DEBUG and self._frame % 30 == 0:
                    print(f"[GAZE] raw=({raw_x:.3f},{raw_y:.3f}) "
                          f"range_x=[{self._rx.lo:.3f},{self._rx.hi:.3f}] "
                          f"norm=({norm_x:.2f},{norm_y:.2f}) "
                          f"screen=({int(self._smooth_x)},{int(self._smooth_y)})"
                          f"{'[SWAPPED]' if self._iris_left_idx != list(IRIS_LEFT_IDX) else ''}")

                # ── Blink detection ────────────────────────────────────────
                ear_l = _ear(lm, EAR_LEFT_IDX, w, h)
                ear_r = _ear(lm, EAR_RIGHT_IDX, w, h)
                avg_ear = (ear_l + ear_r) / 2.0

                if avg_ear < GAZE_BLINK_EAR_THRESHOLD:
                    self._blink_counter += 1
                else:
                    if self._blink_counter >= GAZE_BLINK_FRAMES:
                        # FIX 3: Use confirmation flow for sensitive areas
                        self._handle_blink_click()
                    self._blink_counter = 0

                # ── Telemetry every 300 frames (~5 sec at 60fps) ───────────
                if self._frame % 300 == 0:
                    _track("GazeSessionHeartbeat", {
                        "frame": str(self._frame),
                        "blink_clicks": str(self._blink_count_total),
                        "swap_corrected": str(
                            self._iris_left_idx != list(IRIS_LEFT_IDX)
                        )
                    })

                time.sleep(THREAD_SLEEP_MS / 1000)

        except Exception as exc:
            logger.error("GazeEngine error: %s", exc, exc_info=True)
        finally:
            self._cap.release()
            self._cap = None
            logger.info("GazeEngine stopped")

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="GazeEngine"
        )
        self._thread.start()

    def stop(self):
        self._running = False

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        if enabled:
            # Full reset — iris swap will re-check on next frame
            self._rx = RangeTracker(0.35, 0.65)
            self._ry = RangeTracker(0.30, 0.70)
            self._kx = Kalman1D()
            self._ky = Kalman1D()
            self._blink_counter = 0
            self._frame = 0
            self._iris_swap_checked = False  # Re-verify on next enable
            self._pending_click = False
            logger.info("Gaze ON — look to all 4 screen corners slowly (first 5 sec)")
            _track("GazeEnabled")
        else:
            logger.info("Gaze OFF")
            _track("GazeDisabled", {"total_blink_clicks": str(self._blink_count_total)})


# Singleton
gaze_engine = GazeEngine()
