"""
ui_automation.py — Windows UI Automation for Unified Intent Amplifier.

What this does:
1. BUTTON DETECTION   — finds every clickable button/field in the active window
2. MAGNETIC SNAP      — when gaze gets within SNAP_RADIUS px of a button, cursor
                        locks onto it and glows — blink confirms
3. FORM FILLING       — GPT-4o reads screen, returns field→value pairs,
                        this module types them in order using Tab navigation
4. VOICE COMMANDS     — click/type/focus any element by spoken name

Uses pywinauto (Windows UI Automation API) — no extra Azure cost.
Falls back gracefully if pywinauto not installed.
"""

import threading
import logging
import time
import math
import os

logger = logging.getLogger(__name__)

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0
    _PYAUTOGUI_OK = True
except ImportError:
    _PYAUTOGUI_OK = False

try:
    from pywinauto import Desktop
    from pywinauto.findwindows import ElementNotFoundError
    _WINAUTO_OK = True
except ImportError:
    _WINAUTO_OK = False
    logger.warning("pywinauto not installed — run: pip install pywinauto")

# ── Constants ─────────────────────────────────────────────────────────────────
SNAP_RADIUS      = 55    # px — gaze within this distance snaps to button centre
SNAP_CONFIRM_MS  = 800   # ms gaze must dwell on snapped button before auto-highlight
REFRESH_INTERVAL = 1.5   # seconds between button map refreshes
MAX_BUTTONS      = 30    # max buttons to track at once (performance)


class UIElement:
    """Represents a clickable UI element with its screen position."""
    def __init__(self, name: str, rect, control_type: str = "Button"):
        self.name         = name
        self.rect         = rect          # (left, top, right, bottom)
        self.control_type = control_type
        cx = (rect[0] + rect[2]) // 2
        cy = (rect[1] + rect[3]) // 2
        self.centre       = (cx, cy)

    def __repr__(self):
        return f"<{self.control_type} '{self.name}' at {self.centre}>"


class UIAutomationEngine:
    """
    Detects UI elements in the active window and provides:
    - Magnetic gaze snapping
    - Voice-triggered click/type
    - Automated form filling
    """

    def __init__(self):
        self._elements: list[UIElement] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

        self._snap_enabled = True
        self._snapped_element: UIElement | None = None
        self._snap_dwell_start = 0.0

        # Callbacks set by main.py
        self.on_snap_highlight = None   # (element_name, centre_xy) → overlay shows highlight
        self.on_snap_clear     = None   # () → overlay clears highlight
        self.on_tip            = None   # (text) → overlay tip bar
        self.on_snap_audio     = None   # (cx, cy) → spatial audio cue at button position

    # ── Element detection ─────────────────────────────────────────────────────

    def _get_elements(self) -> list[UIElement]:
        """
        Get all interactive elements in the foreground window using
        Windows UI Automation via pywinauto.
        Falls back to empty list if unavailable.
        """
        if not _WINAUTO_OK:
            return []
        try:
            desktop = Desktop(backend="uia")
            # Get the foreground (active) window
            window = desktop.window(active_only=True)
            elements = []

            # Walk all descendants looking for interactive controls
            for ctrl in window.descendants():
                try:
                    ct = ctrl.element_info.control_type
                    if ct not in ("Button", "Edit", "CheckBox", "RadioButton",
                                  "ComboBox", "Hyperlink", "MenuItem", "ListItem"):
                        continue
                    name = (ctrl.element_info.name or "").strip()
                    if not name or len(name) > 60:
                        continue
                    rect = ctrl.element_info.rectangle
                    if rect.width() < 5 or rect.height() < 5:
                        continue  # invisible element
                    # Check it's actually on screen
                    sw, sh = pyautogui.size()
                    if rect.left < 0 or rect.top < 0 or rect.right > sw or rect.bottom > sh:
                        continue
                    elements.append(UIElement(
                        name=name,
                        rect=(rect.left, rect.top, rect.right, rect.bottom),
                        control_type=ct,
                    ))
                    if len(elements) >= MAX_BUTTONS:
                        break
                except Exception:
                    continue

            return elements

        except Exception as exc:
            logger.debug("UI element scan error: %s", exc)
            return []

    def _refresh_loop(self):
        """Periodically refresh the element map."""
        while self._running:
            elements = self._get_elements()
            with self._lock:
                self._elements = elements
            logger.debug("UI map: %d elements found", len(elements))
            time.sleep(REFRESH_INTERVAL)

    # ── Magnetic snap ─────────────────────────────────────────────────────────

    def check_snap(self, gaze_x: float, gaze_y: float) -> tuple[float, float]:
        """
        Called by gaze engine every frame.
        If gaze is within SNAP_RADIUS of a button centre, returns the
        button's centre (magnetic snap). Otherwise returns gaze unchanged.
        Also highlights the snapped element in the overlay.
        """
        if not self._snap_enabled:
            return gaze_x, gaze_y

        with self._lock:
            elements = list(self._elements)

        best = None
        best_dist = SNAP_RADIUS

        for el in elements:
            cx, cy = el.centre
            dist = math.sqrt((gaze_x - cx) ** 2 + (gaze_y - cy) ** 2)
            if dist < best_dist:
                best_dist = dist
                best = el

        if best:
            # Snapping — return button centre
            if self._snapped_element != best:
                self._snapped_element = best
                self._snap_dwell_start = time.time()
                if self.on_snap_highlight:
                    self.on_snap_highlight(best.name, best.centre)
                # Play spatial audio cue at button position
                if self.on_snap_audio:
                    self.on_snap_audio(best.centre[0], best.centre[1])
                logger.debug("Snap → %s at %s", best.name, best.centre)
            return float(best.centre[0]), float(best.centre[1])
        else:
            # Not near any button
            if self._snapped_element is not None:
                self._snapped_element = None
                if self.on_snap_clear:
                    self.on_snap_clear()
            return gaze_x, gaze_y

    def get_snapped_element(self) -> "UIElement | None":
        """Return the currently snapped element, if any."""
        return self._snapped_element

    # ── Voice-triggered actions ───────────────────────────────────────────────

    def click_element_by_name(self, name: str) -> bool:
        """
        Find element whose name contains `name` (case-insensitive) and click it.
        Called by voice command engine: "click Apply" → clicks Apply button.
        Returns True if found and clicked.
        """
        with self._lock:
            elements = list(self._elements)

        name_lower = name.lower().strip()
        best = None
        for el in elements:
            if name_lower in el.name.lower():
                best = el
                break  # take first match

        if best and _PYAUTOGUI_OK:
            logger.info("Voice click: '%s' at %s", best.name, best.centre)
            pyautogui.click(best.centre[0], best.centre[1], _pause=False)
            if self.on_tip:
                self.on_tip(f"✓ Clicked: {best.name}")
            return True

        logger.warning("Could not find element matching '%s'", name)
        if self.on_tip:
            self.on_tip(f"⚠ Could not find button: {name}")
        return False

    def focus_field_by_name(self, name: str) -> bool:
        """
        Click into an input field by name so user can type into it.
        Called by voice: "go to email field" / "open first name"
        """
        return self.click_element_by_name(name)

    def type_into_focused(self, text: str):
        """Type text into whatever field currently has focus."""
        if _PYAUTOGUI_OK:
            pyautogui.typewrite(text, interval=0.04)
            logger.info("Typed: '%s'", text)

    def press_key(self, key: str):
        """Press a keyboard key by name: tab, enter, escape, pagedown etc."""
        if _PYAUTOGUI_OK:
            pyautogui.press(key)
            logger.info("Key: %s", key)

    def scroll(self, direction: str = "down", clicks: int = 3):
        """Scroll the active window."""
        if _PYAUTOGUI_OK:
            amount = -clicks if direction == "down" else clicks
            pyautogui.scroll(amount)

    # ── Automated form filling ────────────────────────────────────────────────

    def fill_form(self, field_values: dict):
        """
        Fill a form automatically given a dict of {field_name: value}.
        Clicks each field by name, types the value, presses Tab to move on.

        field_values example:
          {"First name": "John", "Last name": "Smith", "Email": "j@example.com"}

        Called after GPT-4o analyses the screen and returns field mappings.
        """
        for field_name, value in field_values.items():
            if not value:
                continue
            logger.info("Filling '%s' = '%s'", field_name, value)
            if self.on_tip:
                self.on_tip(f"✏ Filling: {field_name}")
            found = self.click_element_by_name(field_name)
            time.sleep(0.3)
            if found:
                # Clear existing content then type
                pyautogui.hotkey("ctrl", "a")
                time.sleep(0.1)
                pyautogui.typewrite(str(value), interval=0.05)
            time.sleep(0.2)
            self.press_key("tab")
            time.sleep(0.3)

        if self.on_tip:
            self.on_tip("✓ Form filled — review before submitting")

    def list_elements(self) -> list[str]:
        """Return names of all detected elements — for voice 'what can I click?'"""
        with self._lock:
            return [f"{el.control_type}: {el.name}" for el in self._elements]

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._refresh_loop, daemon=True, name="UIAutomation"
        )
        self._thread.start()
        logger.info("UIAutomationEngine started (snap_radius=%dpx)", SNAP_RADIUS)

    def stop(self):
        self._running = False

    def set_snap_enabled(self, enabled: bool):
        self._snap_enabled = enabled
        if not enabled:
            self._snapped_element = None
            if self.on_snap_clear:
                self.on_snap_clear()
        logger.info("Magnetic snap: %s", enabled)


# Singleton
ui_automation = UIAutomationEngine()
