"""
motor_engine.py — Real-time tremor smoothing (Kalman filter) and typing correction.

FIXES APPLIED:
  - Kalman state fully reset on every toggle ON (prevents cursor jump)
  - Tremor severity levels (mild/moderate/severe) auto-tune Q and R
  - Application Insights telemetry on tremor events
  - Velocity bypass threshold scales with severity
  - atexit guard added for clean shutdown
"""

import threading
import time
import logging
import atexit
from collections import defaultdict
import os
import numpy as np
import pyautogui
from pynput import keyboard
from config import (
    KALMAN_Q, KALMAN_R, KALMAN_VELOCITY_BYPASS_PX,
    DOUBLE_KEY_MS, TYPING_CORRECTION_ENABLED, THREAD_SLEEP_MS
)

logger = logging.getLogger(__name__)
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# ── Application Insights (optional — works without it) ─────────────────────
_tc = None
if os.getenv("USE_APP_INSIGHTS", "false").lower() == "true":
    try:
        from applicationinsights import TelemetryClient
        _tc = TelemetryClient(os.getenv("AZURE_APPINSIGHTS_INSTRUMENTATION_KEY", ""))
        logger.info("App Insights telemetry active in motor_engine")
    except ImportError:
        logger.warning("applicationinsights not installed — telemetry disabled")

def _track(event: str, props: dict = None):
    """Fire an App Insights event if telemetry is available."""
    if _tc:
        try:
            _tc.track_event(event, props or {})
        except Exception:
            pass

# ── Severity presets ────────────────────────────────────────────────────────
# Each level tunes Q (process noise) and R (measurement noise) for the Kalman filter.
# Higher severity = lower Q, higher R = more aggressive smoothing.
SEVERITY_PRESETS = {
    "none":     {"q": 0.01,  "r": 0.5,  "bypass_px": 60},
    "mild":     {"q": 0.005, "r": 2.0,  "bypass_px": 50},
    "moderate": {"q": 0.001, "r": 5.0,  "bypass_px": 40},  # default
    "severe":   {"q": 0.0005,"r": 10.0, "bypass_px": 30},
}


class KalmanFilter1D:
    """1-D Kalman filter for smoothing a noisy scalar signal."""

    def __init__(self, q: float = KALMAN_Q, r: float = KALMAN_R):
        self.q = q
        self.r = r
        self.x = 0.0
        self.p = 1.0

    def update(self, measurement: float) -> float:
        """Apply one Kalman step and return smoothed value."""
        self.p += self.q
        k = self.p / (self.p + self.r)
        self.x += k * (measurement - self.x)
        self.p *= (1 - k)
        return self.x

    def reset(self, value: float = 0.0) -> None:
        """FIX: Full state reset — clears both position estimate and covariance."""
        self.x = value
        self.p = 1.0  # Reset covariance to initial uncertainty


class TremorSmoother:
    """Applies Kalman filters to both X and Y mouse axes with velocity bypass."""

    def __init__(self):
        self.kf_x = KalmanFilter1D()
        self.kf_y = KalmanFilter1D()
        self._prev_x = 0.0
        self._prev_y = 0.0
        self._bypass_px = KALMAN_VELOCITY_BYPASS_PX
        self._tremor_event_count = 0

    def set_severity(self, level: str) -> None:
        """Tune filter parameters to user's tremor severity level."""
        preset = SEVERITY_PRESETS.get(level, SEVERITY_PRESETS["moderate"])
        self.kf_x.q = preset["q"]
        self.kf_x.r = preset["r"]
        self.kf_y.q = preset["q"]
        self.kf_y.r = preset["r"]
        self._bypass_px = preset["bypass_px"]
        logger.info("Tremor severity set to '%s' — Q=%.4f R=%.1f bypass=%dpx",
                    level, preset["q"], preset["r"], preset["bypass_px"])
        _track("TremorSeveritySet", {"level": level, "q": str(preset["q"]), "r": str(preset["r"])})

    def smooth(self, x: float, y: float) -> tuple:
        """
        Return Kalman-smoothed (x, y).
        Fast intentional moves bypass the filter entirely.
        """
        dx = abs(x - self._prev_x)
        dy = abs(y - self._prev_y)

        if dx > self._bypass_px or dy > self._bypass_px:
            # Intentional fast move — reseed filter at new position
            self.kf_x.reset(x)
            self.kf_y.reset(y)
            self._prev_x = x
            self._prev_y = y
            return x, y

        sx = self.kf_x.update(x)
        sy = self.kf_y.update(y)

        # Track tremor correction magnitude for App Insights
        correction = ((sx - x) ** 2 + (sy - y) ** 2) ** 0.5
        if correction > 3.0:  # Only track meaningful corrections
            self._tremor_event_count += 1
            if self._tremor_event_count % 60 == 0:  # Log every 60 events (~1/sec at 60Hz)
                _track("TremorCorrectionApplied", {"magnitude_px": f"{correction:.1f}"})

        self._prev_x = x
        self._prev_y = y
        return sx, sy

    def reset(self, x: float = 0.0, y: float = 0.0) -> None:
        """FIX: Full reset of both filters — call this every time tremor is toggled ON."""
        self.kf_x.reset(x)
        self.kf_y.reset(y)
        self._prev_x = x
        self._prev_y = y
        logger.debug("TremorSmoother fully reset at (%.0f, %.0f)", x, y)


class TypingCorrector:
    """Suppresses accidental double-keystrokes within a configurable time window."""

    def __init__(self, window_ms: int = DOUBLE_KEY_MS):
        self.window_ms = window_ms
        self._last_press: dict = defaultdict(float)
        self._lock = threading.Lock()
        self._suppressed_count = 0

    def is_duplicate(self, key_str: str) -> bool:
        """Return True if this key was pressed within the suppression window."""
        now = time.time() * 1000
        with self._lock:
            last = self._last_press[key_str]
            if now - last < self.window_ms:
                self._suppressed_count += 1
                if self._suppressed_count % 10 == 0:
                    _track("TypingCorrectionApplied", {"count": str(self._suppressed_count)})
                return True
            self._last_press[key_str] = now
            return False


class MotorEngine:
    """Tremor smoothing (mouse) + typing correction (keyboard)."""

    def __init__(self):
        self.smoother = TremorSmoother()
        self.corrector = TypingCorrector()
        self.tremor_enabled = False
        self.typing_enabled = TYPING_CORRECTION_ENABLED
        self._running = False
        self._tremor_thread = None
        self._kb_listener = None
        self._kb_controller = keyboard.Controller()
        self._severity = "moderate"
        # Register clean shutdown on process exit
        atexit.register(self.stop)

    def _tremor_loop(self) -> None:
        """
        60Hz polling loop: reads raw cursor position, applies Kalman filter,
        moves cursor to smoothed position.
        """
        logger.info("Tremor smoothing loop started (Q=%.4f, R=%.1f)", KALMAN_Q, KALMAN_R)
        while self._running:
            if self.tremor_enabled:
                try:
                    x, y = pyautogui.position()
                    sx, sy = self.smoother.smooth(float(x), float(y))
                    sx_i, sy_i = int(sx), int(sy)
                    if abs(sx_i - x) >= 2 or abs(sy_i - y) >= 2:
                        pyautogui.moveTo(sx_i, sy_i, _pause=False)
                except Exception:
                    pass
            time.sleep(THREAD_SLEEP_MS / 1000)  # ~60Hz

    def _on_press(self, key) -> None:
        """Intercept key press — suppress if it's a rapid duplicate."""
        if not self.typing_enabled:
            return
        try:
            key_str = key.char if hasattr(key, "char") and key.char else str(key)
        except Exception:
            key_str = str(key)

        if self.corrector.is_duplicate(key_str):
            logger.debug("Suppressed duplicate keystroke: %s", key_str)
            return False  # Suppress — requires running as Administrator on Windows

    def start(self) -> None:
        """Start tremor polling loop and keyboard listener."""
        if self._running:
            return
        self._running = True

        self._tremor_thread = threading.Thread(
            target=self._tremor_loop, daemon=True, name="TremorLoop"
        )
        self._tremor_thread.start()

        self._kb_listener = keyboard.Listener(on_press=self._on_press)
        self._kb_listener.daemon = True
        self._kb_listener.start()

        logger.info("MotorEngine started")
        _track("MotorEngineStarted")

    def stop(self) -> None:
        """Stop all listeners cleanly."""
        self._running = False
        if self._kb_listener:
            try:
                self._kb_listener.stop()
            except Exception:
                pass
        logger.info("MotorEngine stopped")

    def set_tremor(self, enabled: bool) -> None:
        """
        FIX: Enable or disable tremor smoothing.
        Always does a full Kalman state reset when enabling
        to prevent cursor jumping to stale filter position.
        """
        self.tremor_enabled = enabled
        if enabled:
            x, y = pyautogui.position()
            # FIX: Full reset — clears covariance matrix AND position estimate
            self.smoother.reset(float(x), float(y))
            logger.info("Tremor smoothing ON — filter reset and seeded at (%d, %d)", x, y)
            _track("TremorSmoothingEnabled", {"seed_x": str(x), "seed_y": str(y)})
        else:
            logger.info("Tremor smoothing OFF")
            _track("TremorSmoothingDisabled")

    def set_severity(self, level: str) -> None:
        """Set tremor severity — tunes Kalman parameters automatically."""
        self._severity = level
        self.smoother.set_severity(level)
        # If tremor is active, reset the filter with new parameters
        if self.tremor_enabled:
            x, y = pyautogui.position()
            self.smoother.reset(float(x), float(y))

    def set_typing(self, enabled: bool) -> None:
        self.typing_enabled = enabled
        logger.info("Typing correction: %s", enabled)
        _track("TypingCorrectionToggled", {"enabled": str(enabled)})


# Singleton
motor_engine = MotorEngine()
