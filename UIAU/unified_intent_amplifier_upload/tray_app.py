"""
tray_app.py — System tray icon (pystray). Runs in a NON-daemon thread.
"""

import threading
import logging
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

try:
    import pystray
    _TRAY_AVAILABLE = True
except ImportError:
    _TRAY_AVAILABLE = False
    logger.warning("pystray not installed — tray disabled")


def _make_icon(size: int = 64) -> Image.Image:
    """Generate tray icon programmatically — no image file needed."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size - 2, size - 2], fill="#00d4ff")
    cx = size // 2
    draw.ellipse([cx - 8, cx - 8, cx + 8, cx + 8], fill="#ffffff")
    draw.ellipse([cx - 3, cx - 3, cx + 3, cx + 3], fill="#000000")
    return img


class TrayApp:
    """System tray app. NON-daemon thread so Windows doesn't kill it."""

    def __init__(self, overlay=None):
        self.overlay = overlay
        self._icon = None
        self._thread = None

        self.state = {
            "gaze":      False,
            "tremor":    False,
            "typing":    True,
            "audio":     False,
            "cognitive": False,
        }

    def _toggle(self, feature: str) -> None:
        from gaze_engine import gaze_engine
        from motor_engine import motor_engine
        from audio_engine import audio_engine

        new_val = not self.state[feature]
        self.state[feature] = new_val

        if feature == "gaze":
            gaze_engine.set_enabled(new_val)
        elif feature == "tremor":
            motor_engine.set_tremor(new_val)
        elif feature == "typing":
            motor_engine.set_typing(new_val)
        elif feature == "audio":
            audio_engine.set_spatial_enabled(new_val)

        if self.overlay:
            self.overlay.set_indicator(feature, new_val)
            label = feature.replace("_", " ").title()
            self.overlay.show_tip(f"{'ON ✓' if new_val else 'OFF'}: {label}")

        logger.info("Tray: %s → %s", feature, new_val)
        if self._icon:
            self._icon.update_menu()

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem("Unified Intent Amplifier", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("👁  Gaze Control",
                lambda i, it: self._toggle("gaze"),
                checked=lambda it: self.state["gaze"]),
            pystray.MenuItem("🖱  Tremor Smoothing",
                lambda i, it: self._toggle("tremor"),
                checked=lambda it: self.state["tremor"]),
            pystray.MenuItem("⌨  Typing Correction",
                lambda i, it: self._toggle("typing"),
                checked=lambda it: self.state["typing"]),
            pystray.MenuItem("🔊  Spatial Audio",
                lambda i, it: self._toggle("audio"),
                checked=lambda it: self.state["audio"]),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

    def _quit(self, icon, item) -> None:
        logger.info("Quit from tray")
        icon.stop()

    def _run_tray(self) -> None:
        if not _TRAY_AVAILABLE:
            return
        self._icon = pystray.Icon(
            "UnifiedIntentAmplifier",
            _make_icon(),
            "Unified Intent Amplifier",
            self._build_menu(),
        )
        logger.info("Tray icon running")
        self._icon.run()
        logger.info("Tray icon stopped")

    def start(self) -> None:
        if not _TRAY_AVAILABLE:
            logger.warning("pystray unavailable — tray skipped")
            return
        # daemon=False: Windows won't silently kill this thread
        self._thread = threading.Thread(
            target=self._run_tray, daemon=False, name="TrayApp")
        self._thread.start()
        logger.info("TrayApp started (non-daemon)")

    def stop(self) -> None:
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
