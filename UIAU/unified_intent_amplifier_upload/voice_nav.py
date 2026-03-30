"""
voice_nav.py — Always-on voice navigation for Unified Intent Amplifier.

What this does:
1. MIC CHECK      — on startup, tests the mic and shows a clear message if blocked
2. PUSH-TO-TALK   — press and hold F4 to speak a command (no accidental triggers)
3. COMMANDS       — understands natural speech and maps to actions:
     "click [name]"       → clicks button/link by name via UIAutomation
     "type [text]"        → types text into focused field
     "scroll down/up"     → scrolls the page
     "next field"         → presses Tab
     "go back"            → presses Escape
     "read screen"        → triggers cognitive engine screen read
     "fill form"          → asks GPT-4o to fill current form
     "submit" / "enter"   → presses Enter
     "what can I click"   → lists all detected buttons aloud
     anything else        → sent to GPT-4o as a question with screen context
4. CONTINUOUS     — runs in background, always ready
"""

import os
import time
import threading
import logging
import tempfile

logger = logging.getLogger(__name__)

# ── Optional imports ──────────────────────────────────────────────────────────
try:
    import sounddevice as sd
    import numpy as np
    _SD_OK = True
except ImportError:
    _SD_OK = False
    logger.warning("sounddevice not installed — voice nav disabled")

try:
    import pyautogui
    _PYA_OK = True
except ImportError:
    _PYA_OK = False

try:
    from pynput import keyboard as _kb
    _PYNPUT_OK = True
except ImportError:
    _PYNPUT_OK = False

# ── Constants ─────────────────────────────────────────────────────────────────
PUSH_TO_TALK_KEY  = _kb.Key.f4 if _PYNPUT_OK else None  # Hold F4 to speak
SAMPLE_RATE       = 16000
MAX_RECORD_S      = 8        # max seconds per command
SILENCE_THRESHOLD = 0.001    # RMS below this = silence (mic muted / wrong device)


class VoiceNavEngine:
    """
    Always-on voice navigation engine.
    Push and hold F4 → speak → release → command executes.
    """

    def __init__(self):
        self._running   = False
        self._recording = False
        self._thread    = None
        self._whisper   = None
        self._audio_buf = []
        self._hotkey_held = False

        # Injected by main.py
        self.ui_automation   = None   # UIAutomationEngine
        self.cognitive_engine = None  # for read_screen_now
        self.ai_assistant    = None   # for ask_question
        self.on_tip          = None   # overlay tip
        self.on_speak        = None   # audio_engine.speak
        self.on_listening_start = None   # overlay shows 🎤
        self.on_listening_stop  = None   # overlay hides 🎤

    def set_whisper(self, model):
        self._whisper = model

    # ── Mic health check ──────────────────────────────────────────────────────

    def check_mic(self) -> tuple[bool, str]:
        """
        Test the microphone on startup.
        Returns (ok: bool, message: str).
        Shows a clear, actionable message if mic is blocked.
        """
        if not _SD_OK:
            return False, "sounddevice not installed — pip install sounddevice"

        try:
            # Try to record 0.5s of silence/audio
            test = sd.rec(int(0.5 * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                          channels=1, dtype="float32")
            sd.wait()
            rms = float(np.sqrt(np.mean(test ** 2)))
            dev = sd.query_devices(sd.default.device[0], "input")
            dev_name = dev.get("name", "unknown")

            if rms < SILENCE_THRESHOLD:
                msg = (
                    f"⚠ Mic '{dev_name}' is connected but silent. "
                    f"To fix: Windows Settings → Privacy & Security → Microphone "
                    f"→ turn ON 'Let desktop apps access your microphone'. "
                    f"Then restart the app."
                )
                logger.warning("Mic silent: RMS=%.5f device='%s'", rms, dev_name)
                return False, msg
            else:
                msg = f"✓ Mic ready: {dev_name}"
                logger.info("Mic OK: RMS=%.5f device='%s'", rms, dev_name)
                return True, msg

        except Exception as exc:
            msg = (
                f"⚠ Cannot access microphone: {exc}. "
                f"Check: Windows Settings → Privacy → Microphone → allow desktop apps."
            )
            logger.warning("Mic check failed: %s", exc)
            return False, msg

    # ── Recording ─────────────────────────────────────────────────────────────

    def _record_until_release(self) -> np.ndarray | None:
        """
        Stream audio from mic while F4 is held.
        Returns numpy array of audio, or None if silent.
        """
        if not _SD_OK:
            return None

        frames = []
        logger.info("Voice: recording started (F4 held)")

        def _callback(indata, frame_count, time_info, status):
            frames.append(indata.copy())

        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                dtype="float32", callback=_callback):
                start = time.time()
                while self._hotkey_held and (time.time() - start) < MAX_RECORD_S:
                    time.sleep(0.05)

            if not frames:
                return None

            audio = np.concatenate(frames, axis=0)
            rms = float(np.sqrt(np.mean(audio ** 2)))
            logger.info("Voice: recorded %.1fs RMS=%.5f",
                        len(audio) / SAMPLE_RATE, rms)

            if rms < SILENCE_THRESHOLD:
                logger.warning("Voice: recording was silent — mic muted?")
                if self.on_tip:
                    self.on_tip("⚠ Mic silent — check Settings → Privacy → Microphone")
                if self.on_speak:
                    self.on_speak("I could not hear you. Please check your microphone in Windows Settings.")
                return None

            return audio

        except Exception as exc:
            logger.error("Voice record error: %s", exc)
            return None


    def _transcribe(self, audio) -> str:
        """
        Transcribe audio numpy array using Whisper.
        Writes to a named temp file with explicit path (not NamedTemporaryFile)
        so Windows does not lock the file while Whisper reads it.
        """
        if self._whisper is None:
            logger.warning("Transcribe called but Whisper not loaded yet")
            return ""
        import os
        import tempfile
        import numpy as np
        import scipy.io.wavfile as wav

        tmp_path = None
        try:
            # Ensure audio is a numpy float32 array
            audio_arr = np.array(audio, dtype=np.float32).flatten()

            # Check volume — silent recording means mic blocked
            rms = float(np.sqrt(np.mean(audio_arr ** 2)))
            logger.info("Transcribe: audio length=%.1fs RMS=%.5f",
                        len(audio_arr) / SAMPLE_RATE, rms)
            if rms < 0.0008:
                logger.warning("Audio too quiet to transcribe (RMS=%.5f)", rms)
                return ""

            # Convert float32 [-1,1] to int16 for WAV
            audio_int16 = (np.clip(audio_arr, -1.0, 1.0) * 32767).astype(np.int16)

            # Use a fixed filename per process — safe on Windows
            tmp_dir = tempfile.gettempdir()
            tmp_path = os.path.join(tmp_dir, f"fia_voice_{os.getpid()}.wav")

            # Write WAV
            wav.write(tmp_path, SAMPLE_RATE, audio_int16)

            # Verify file was written
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 100:
                logger.error("WAV file not written correctly: %s", tmp_path)
                return ""

            # Transcribe
            result = self._whisper.transcribe(tmp_path, fp16=False,
                                               language="en")
            text = result.get("text", "").strip()
            logger.info("Whisper result: '%s'", text)
            return text.lower()

        except Exception as exc:
            logger.error("Transcribe error: %s", exc, exc_info=True)
            return ""
        finally:
            # Always clean up — but only after Whisper is done
            if tmp_path:
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass

    # ── Command parsing ───────────────────────────────────────────────────────

    def _handle_command(self, text: str):
        """
        Parse transcribed speech and execute the right action.
        Order matters — more specific patterns checked first.
        """
        if not text:
            return

        t = text.lower().strip().rstrip(".")
        logger.info("Voice command: '%s'", t)

        if self.on_tip:
            self.on_tip(f"🎤 Heard: \"{text}\"")

        # ── Navigation commands ───────────────────────────────────────────────
        if t in ("submit", "enter", "send", "go", "confirm"):
            if _PYA_OK:
                pyautogui.press("enter")
            if self.on_tip:
                self.on_tip("↵ Enter pressed")

        elif t in ("next field", "next", "tab"):
            if _PYA_OK:
                pyautogui.press("tab")
            if self.on_tip:
                self.on_tip("⇥ Tab — moved to next field")

        elif t in ("previous field", "previous", "back field"):
            if _PYA_OK:
                pyautogui.hotkey("shift", "tab")

        elif t in ("go back", "back", "escape", "cancel"):
            if _PYA_OK:
                pyautogui.press("escape")

        elif any(t.startswith(p) for p in ("scroll down", "page down", "down")):
            if self.ui_automation:
                self.ui_automation.scroll("down")
            elif _PYA_OK:
                pyautogui.scroll(-5)

        elif any(t.startswith(p) for p in ("scroll up", "page up", "up")):
            if self.ui_automation:
                self.ui_automation.scroll("up")
            elif _PYA_OK:
                pyautogui.scroll(5)

        # ── Mouse movement by voice ──────────────────────────────────────────
        elif any(t.startswith(p) for p in ("move mouse", "move cursor", "mouse to",
                                            "cursor to", "go to corner", "move to")):
            self._move_mouse_by_voice(t)

        # ── Click by name ─────────────────────────────────────────────────────
        elif t.startswith("click ") or t.startswith("press ") or t.startswith("select "):
            target = t.split(" ", 1)[1].strip()
            if self.ui_automation:
                found = self.ui_automation.click_element_by_name(target)
                if not found and self.on_speak:
                    self.on_speak(f"I could not find a button called {target}")
            elif _PYA_OK:
                # Fallback: just say what to click
                if self.on_speak:
                    self.on_speak(f"Look for the {target} button and blink on it")

        # ── Type text ─────────────────────────────────────────────────────────
        elif t.startswith("type ") or t.startswith("write ") or t.startswith("enter "):
            text_to_type = t.split(" ", 1)[1].strip()
            if self.ui_automation:
                self.ui_automation.type_into_focused(text_to_type)
            elif _PYA_OK:
                pyautogui.typewrite(text_to_type, interval=0.05)
            if self.on_tip:
                self.on_tip(f"⌨ Typed: {text_to_type}")

        # ── Focus a field ─────────────────────────────────────────────────────
        elif t.startswith("go to ") or t.startswith("open ") or t.startswith("focus "):
            field = t.split(" ", 2)[-1].strip()
            if self.ui_automation:
                self.ui_automation.focus_field_by_name(field)

        # ── Screen read ───────────────────────────────────────────────────────
        elif any(t == p for p in ("read screen", "read", "what is on screen",
                                   "what do you see", "describe screen",
                                   "what's on my screen", "whats on screen")):
            # Debug: Check AI state using getter
            ai_enabled = self.cognitive_engine and hasattr(self.cognitive_engine, "get_enabled") and self.cognitive_engine.get_enabled()
            logger.info("Read screen command | AI enabled: %s", ai_enabled)
            
            # Only use cognitive engine if AI Assist is enabled
            if not ai_enabled:
                if self.on_tip:
                    self.on_tip("🧠 AI Assist is OFF - Enable it in overlay for screen reading")
                if self.on_speak:
                    self.on_speak("AI Assist is disabled. Enable it in the overlay to read your screen.")
                return
                
            if self.on_tip:
                self.on_tip("📸 Reading your screen — one moment...")
            if self.on_speak:
                self.on_speak("Reading your screen now.")
            if self.cognitive_engine:
                threading.Thread(target=self.cognitive_engine.read_screen_now,
                                  daemon=True).start()

        # ── Fill form ─────────────────────────────────────────────────────────
        elif any(t == p for p in ("fill form", "fill in form", "complete form",
                                   "fill application", "autofill")):
            threading.Thread(target=self._auto_fill_form, daemon=True).start()

        # ── What can I click ──────────────────────────────────────────────────
        elif any(t == p for p in ("what can i click", "what buttons",
                                   "list buttons", "what's here", "options")):
            # Only use AI if cognitive engine is enabled
            ai_enabled = self.cognitive_engine and hasattr(self.cognitive_engine, "get_enabled") and self.cognitive_engine.get_enabled()
            if not ai_enabled:
                if self.on_tip:
                    self.on_tip("🧠 AI Assist is OFF - Enable it to see buttons")
                if self.on_speak:
                    self.on_speak("AI Assist is disabled. Enable it in the overlay to list buttons.")
                return
            
            if self.ui_automation:
                items = self.ui_automation.list_elements()
                if items:
                    summary = ", ".join(i.split(": ", 1)[-1] for i in items[:8])
                    if self.on_speak:
                        self.on_speak(f"I can see: {summary}")
                    if self.on_tip:
                        self.on_tip(f"Buttons: {summary}")
                else:
                    if self.on_speak:
                        self.on_speak("I could not detect any buttons. Try reading the screen first.")

        # ── Stop / mute voice nav ─────────────────────────────────────────────
        elif t in ("stop listening", "quiet", "mute", "pause"):
            if self.on_tip:
                self.on_tip("🔇 Voice nav paused — press F4 to resume")

        # ── Unknown — ask GPT-4o like ChatGPT/Claude ────────────────────────
        else:
            # Debug: Check AI state using getter
            ai_enabled = self.cognitive_engine and hasattr(self.cognitive_engine, "get_enabled") and self.cognitive_engine.get_enabled()
            logger.info("Voice command: '%s' | AI enabled: %s", text, ai_enabled)
            
            # ONLY use AI if AI Assist is enabled - no fallback
            if ai_enabled:
                if hasattr(self.cognitive_engine, "answer_question"):
                    self.cognitive_engine.answer_question(text)
            else:
                # AI is disabled - do NOT use ai_assistant either
                if self.on_speak:
                    self.on_speak("I heard you but AI Assist is disabled. Enable it in the overlay to get AI help.")
                if self.on_tip:
                    self.on_tip("🧠 AI Assist is OFF - Enable it in overlay for AI help")

    def _move_mouse_by_voice(self, command: str):
        """
        Move the mouse cursor by voice command.
        Supports: corners, edges, centre, relative movements, percentages.
        Examples: "move mouse to top right", "cursor to centre",
                  "move left", "move to bottom", "mouse to 50 percent down"
        """
        if not _PYA_OK:
            return
        try:
            sw, sh = pyautogui.size()
            t = command.lower()

            # Named positions
            positions = {
                ("top left", "upper left", "top-left"):       (50, 50),
                ("top right", "upper right", "top-right"):    (sw-50, 50),
                ("bottom left", "lower left", "bottom-left"): (50, sh-50),
                ("bottom right", "lower right", "bottom-right"): (sw-50, sh-50),
                ("centre", "center", "middle"):               (sw//2, sh//2),
                ("top", "up top"):                            (sw//2, 50),
                ("bottom", "down bottom"):                    (sw//2, sh-50),
                ("left", "far left"):                         (50, sh//2),
                ("right", "far right"):                       (sw-50, sh//2),
            }

            cx, cy = pyautogui.position()  # current position

            for keys, (tx, ty) in positions.items():
                if isinstance(keys, str):
                    keys = (keys,)
                if any(k in t for k in keys):
                    pyautogui.moveTo(tx, ty, duration=0.3, _pause=False)
                    label = [k for k in keys if k in t][0]
                    if self.on_tip:
                        self.on_tip(f"🖱 Mouse → {label}")
                    return

            # Relative movement — "move left a bit", "move down"
            step = 150
            if "left" in t and "right" not in t:
                pyautogui.moveTo(max(0, cx - step), cy, duration=0.2, _pause=False)
            elif "right" in t and "left" not in t:
                pyautogui.moveTo(min(sw, cx + step), cy, duration=0.2, _pause=False)
            elif "up" in t and "down" not in t:
                pyautogui.moveTo(cx, max(0, cy - step), duration=0.2, _pause=False)
            elif "down" in t and "up" not in t:
                pyautogui.moveTo(cx, min(sh, cy + step), duration=0.2, _pause=False)
            if self.on_tip:
                self.on_tip(f"🖱 Mouse moved")

        except Exception as exc:
            logger.warning("Mouse move error: %s", exc)

    def _auto_fill_form(self):
        # Debug: Check AI state using getter
        ai_enabled = self.cognitive_engine and hasattr(self.cognitive_engine, "get_enabled") and self.cognitive_engine.get_enabled()
        logger.info("Fill form command | AI enabled: %s", ai_enabled)
        
        # Only use AI team if cognitive engine is enabled
        if not ai_enabled:
            if self.on_tip:
                self.on_tip("🧠 AI Assist is OFF - Enable it in overlay for form filling")
            if self.on_speak:
                self.on_speak("AI Assist is disabled. Enable it in the overlay to use form filling.")
            return
        
        if self.on_tip:
            self.on_tip("🧠 Agent team is reading the form...")
        if self.on_speak:
            self.on_speak("Let me read the form and fill it in for you.")
        try:
            from agent_team import agent_team
            agent_team.run_async("fill form — analyse screen and fill all visible fields")
        except Exception as exc:
            logger.error("Auto fill error: %s", exc)
            if self.on_speak:
                self.on_speak("Something went wrong. Please try again.")

    # ── Push-to-talk hotkey ───────────────────────────────────────────────────

    def _setup_hotkey(self):
        """Set up F4 push-to-talk listener using pynput."""
        if not _PYNPUT_OK:
            logger.warning("pynput not installed — push-to-talk unavailable")
            return

        def on_press(key):
            if key == PUSH_TO_TALK_KEY and not self._hotkey_held:
                self._hotkey_held = True
                self._start_listening()

        def on_release(key):
            if key == PUSH_TO_TALK_KEY:
                self._hotkey_held = False

        listener = _kb.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()
        logger.info("Push-to-talk: hold F4 to speak a command")

    def _start_listening(self):
        """Called when F4 is pressed — records and processes command."""
        if not self._running:
            return

        def _do():
            if self.on_listening_start:
                self.on_listening_start()
            if self.on_tip:
                self.on_tip("🎤 Listening — speak your command... (release F4 when done)")

            audio = self._record_until_release()

            if self.on_listening_stop:
                self.on_listening_stop()

            if audio is not None:
                text = self._transcribe(audio)
                if text:
                    self._handle_command(text)
                else:
                    if self.on_tip:
                        self.on_tip("⚠ Could not understand — please speak clearly and try again")

        threading.Thread(target=_do, daemon=True, name="VoiceCommand").start()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self, whisper_model=None):
        if whisper_model:
            self._whisper = whisper_model
        self._running = True

        # Check mic on startup — show message immediately
        ok, msg = self.check_mic()
        if self.on_tip:
            self.on_tip(msg)
        if self.on_speak and not ok:
            self.on_speak(msg)

        # Open Windows mic settings if mic check failed
        if not ok:
            import subprocess, sys
            if self.on_tip:
                self.on_tip("⚠ Opening Windows microphone settings — enable access then restart")
            if self.on_speak:
                self.on_speak(
                    "Your microphone needs permission. "
                    "I am opening Windows settings now. "
                    "Turn on microphone access for desktop apps, then restart the application."
                )
            try:
                # Open Windows Privacy > Microphone settings directly
                subprocess.Popen(
                    ["ms-settings:privacy-microphone"],
                    shell=True
                )
            except Exception:
                pass

        # Set up push-to-talk
        self._setup_hotkey()
        logger.info("VoiceNavEngine started — hold F4 to speak")

    def stop(self):
        self._running = False


# Singleton
voice_nav = VoiceNavEngine()
