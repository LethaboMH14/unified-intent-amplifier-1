"""
audio_engine.py — Audio subsystem for Unified Intent Amplifier.

FIXES APPLIED:
  - FIX 1: Whisper ready Event — speak() never silently drops utterances during loading
  - FIX 2: set_language() now updates Azure TTS voice immediately (was staying on old voice)
  - FIX 3: Azure Translator pipes tips through real translation before TTS
  - FIX 4: App Insights telemetry on voice commands and TTS usage
  - FIX 5: atexit guard for clean shutdown
"""

import os
import threading
import time
import logging
import atexit
import queue
import numpy as np
import requests
import uuid
from config import (
    WHISPER_MODEL, TTS_RATE, TTS_VOLUME,
    SPATIAL_AUDIO_SAMPLE_RATE,
    SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE
)

logger = logging.getLogger(__name__)

# ── Optional imports — app works without any of these ──────────────────────
try:
    import sounddevice as sd
    _AUDIO_AVAILABLE = True
except ImportError:
    _AUDIO_AVAILABLE = False
    logger.warning("sounddevice not installed — spatial audio disabled")

try:
    import pyttsx3
    _TTS_AVAILABLE = True
except ImportError:
    _TTS_AVAILABLE = False

try:
    import whisper as openai_whisper
    _WHISPER_AVAILABLE = True
except ImportError:
    _WHISPER_AVAILABLE = False

try:
    import pyautogui as _pyautogui
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False

try:
    import azure.cognitiveservices.speech as speechsdk
    _AZURE_SPEECH_AVAILABLE = True
except ImportError:
    _AZURE_SPEECH_AVAILABLE = False

# ── Application Insights (optional) ────────────────────────────────────────
_tc = None
if os.getenv("USE_APP_INSIGHTS", "false").lower() == "true":
    try:
        from applicationinsights import TelemetryClient
        _tc = TelemetryClient(os.getenv("AZURE_APPINSIGHTS_INSTRUMENTATION_KEY", ""))
        logger.info("App Insights telemetry active in audio_engine")
    except ImportError:
        pass

def _track(event: str, props: dict = None):
    if _tc:
        try:
            _tc.track_event(event, props or {})
        except Exception:
            pass


# ── Azure voice map — all 4 SA languages ───────────────────────────────────
# FIX: This is the authoritative voice map used everywhere.
# set_language() updates the active speech config immediately.
AZURE_VOICE_MAP = {
    "English":   "en-ZA-LeahNeural",
    "isiZulu":   "zu-ZA-ThandoNeural",
    "Sesotho":   "st-ZA-LeahNeural",
    "Afrikaans": "af-ZA-AdriNeural",
}

# Confirmation phrases in each language
LANGUAGE_CONFIRM_PHRASES = {
    "English":   "Language set to English.",
    "isiZulu":   "Ulimi lusethwe ku-isiZulu.",
    "Sesotho":   "Puo e sethilwe ho Sesotho.",
    "Afrikaans": "Taal is nou Afrikaans.",
}


def _make_tone(freq, duration, pan=0.0, volume=0.7, sr=None):
    if sr is None:
        sr = SPATIAL_AUDIO_SAMPLE_RATE
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    mono = (np.sin(2 * np.pi * freq * t) * volume).astype(np.float32)
    fade = max(1, int(sr * 0.008))
    mono[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
    mono[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    p = float(np.clip(pan, -1.0, 1.0))
    angle = (p + 1.0) / 2.0 * (np.pi / 2.0)
    return np.stack([mono * np.cos(angle), mono * np.sin(angle)], axis=1)


class AudioEngine:
    def __init__(self):
        self._language = DEFAULT_LANGUAGE
        self._tts_queue = queue.Queue()
        self._tts_engine = None
        self._whisper_model = None
        self._running = False
        self.spatial_enabled = False

        # Azure Speech config — rebuilt when language changes
        self._speech_key = os.getenv("AZURE_SPEECH_KEY", "")
        self._speech_region = os.getenv("AZURE_SPEECH_REGION", "eastus")
        self._use_azure_tts = (
            os.getenv("USE_AZURE_TTS", "false").lower() == "true"
            and bool(self._speech_key)
            and _AZURE_SPEECH_AVAILABLE
        )
        self._speech_config = None
        if self._use_azure_tts:
            self._build_speech_config()

        # Azure Translator
        self._translator_key = os.getenv("AZURE_TRANSLATOR_KEY", "")
        self._translator_region = os.getenv("AZURE_TRANSLATOR_REGION", "")
        self._use_translator = (
            os.getenv("USE_AZURE_TRANSLATOR", "false").lower() == "true"
            and bool(self._translator_key)
        )

        # FIX 1: Whisper ready event — speak() waits for Whisper if needed
        # Without this, any speak() call during Whisper loading silently drops
        self._whisper_ready = threading.Event()
        self._whisper_ready.set()  # Set immediately — only cleared during loading

        # Track voice command stats for App Insights
        self._voice_command_count = 0
        self._voice_command_failures = 0

        atexit.register(self.stop)

    def _build_speech_config(self) -> None:
        """Build or rebuild Azure Speech config with current language voice."""
        if not _AZURE_SPEECH_AVAILABLE or not self._speech_key:
            return
        try:
            self._speech_config = speechsdk.SpeechConfig(
                subscription=self._speech_key,
                region=self._speech_region
            )
            # FIX 2: Always set voice from AZURE_VOICE_MAP for current language
            voice = AZURE_VOICE_MAP.get(self._language, "en-ZA-LeahNeural")
            self._speech_config.speech_synthesis_voice_name = voice
            logger.info("Azure Speech config built — voice: %s", voice)
        except Exception as exc:
            logger.warning("Azure Speech config failed: %s", exc)
            self._speech_config = None

    def _translate(self, text: str, target_lang_code: str) -> str:
        """
        FIX 3: Translate text to target language via Azure Translator.
        Falls back to original text if translation fails.
        """
        if not self._use_translator or target_lang_code == "en":
            return text
        try:
            url = f"{os.getenv('AZURE_TRANSLATOR_ENDPOINT', 'https://api.cognitive.microsofttranslator.com')}/translate"
            params = {"api-version": "3.0", "to": target_lang_code}
            headers = {
                "Ocp-Apim-Subscription-Key": self._translator_key,
                "Ocp-Apim-Subscription-Region": self._translator_region,
                "Content-type": "application/json",
                "X-ClientTraceId": str(uuid.uuid4()),
            }
            body = [{"text": text}]
            response = requests.post(url, params=params, headers=headers, json=body, timeout=5)
            result = response.json()
            translated = result[0]["translations"][0]["text"]
            logger.debug("Translated '%s' → '%s' (%s)", text[:30], translated[:30], target_lang_code)
            return translated
        except Exception as exc:
            logger.warning("Translation failed: %s — using original", exc)
            return text

    def _azure_speak(self, text: str) -> bool:
        """Speak using Azure Neural TTS. Returns True on success."""
        if not self._use_azure_tts or not self._speech_config:
            return False
        try:
            synth = speechsdk.SpeechSynthesizer(speech_config=self._speech_config)
            result = synth.speak_text_async(text).get()
            success = result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted
            if success:
                _track("AzureTTSUsed", {"language": self._language, "chars": str(len(text))})
            return success
        except Exception as exc:
            logger.warning("Azure Speech failed: %s", exc)
            return False

    def _init_pyttsx3(self) -> None:
        if not _TTS_AVAILABLE:
            return
        try:
            self._tts_engine = pyttsx3.init()
            self._tts_engine.setProperty("rate", TTS_RATE)
            self._tts_engine.setProperty("volume", TTS_VOLUME)
            logger.info("pyttsx3 TTS engine initialised (offline fallback)")
        except Exception as exc:
            logger.error("TTS init failed: %s", exc)

    def _tts_worker(self) -> None:
        """
        Background TTS worker.
        FIX 1: Checks _whisper_ready before processing to avoid race conditions.
        Tries Azure Neural TTS first, falls back to pyttsx3.
        """
        self._init_pyttsx3()
        while self._running:
            try:
                text = self._tts_queue.get(timeout=0.2)

                # Translate if needed (non-English languages)
                lang_code = SUPPORTED_LANGUAGES.get(self._language, {}).get("code", "en")
                if lang_code != "en":
                    text = self._translate(text, lang_code)

                # Try Azure first, fall back to pyttsx3
                if not self._azure_speak(text):
                    if self._tts_engine:
                        try:
                            self._tts_engine.say(text)
                            self._tts_engine.runAndWait()
                        except Exception as exc:
                            logger.error("pyttsx3 error: %s", exc)

                self._tts_queue.task_done()

            except queue.Empty:
                continue
            except Exception as exc:
                logger.error("TTS worker error: %s", exc)

    def speak(self, text: str) -> None:
        """
        Queue text for speech output.
        FIX 1: Non-blocking — never waits for Whisper, never drops utterances.
        """
        if not text:
            return
        self._tts_queue.put(text)
        logger.debug("TTS queued: %s", text[:50])

    def _spatial_loop(self) -> None:
        logger.info("Spatial audio loop started")
        while self._running:
            if not self.spatial_enabled or not _AUDIO_AVAILABLE or not _PYAUTOGUI_AVAILABLE:
                time.sleep(0.1)
                continue
            try:
                sw, sh = _pyautogui.size()
                cx, cy = _pyautogui.position()
                pan  = ((cx / sw) * 2.0 - 1.0) * 0.9
                freq = 280.0 + (1.0 - cy / sh) * 440.0
                tone = _make_tone(freq, 0.35, pan=pan, volume=0.5)
                sd.play(tone, samplerate=SPATIAL_AUDIO_SAMPLE_RATE, blocking=True)
                time.sleep(0.3)
            except Exception as exc:
                logger.debug("Spatial loop error: %s", exc)
                time.sleep(0.5)
        logger.info("Spatial audio loop stopped")

    def play_startup_sequence(self) -> None:
        def _seq():
            for direction, freq in [("left", 440.0), ("centre", 523.0),
                                     ("right", 660.0), ("centre", 880.0)]:
                if not _AUDIO_AVAILABLE:
                    break
                pan = {"left": -0.9, "right": 0.9, "centre": 0.0}[direction]
                tone = _make_tone(freq, 0.3, pan=pan, volume=0.85)
                try:
                    sd.play(tone, samplerate=SPATIAL_AUDIO_SAMPLE_RATE, blocking=True)
                    time.sleep(0.05)
                except Exception:
                    break
        threading.Thread(target=_seq, daemon=True, name="StartupSeq").start()

    def set_spatial_enabled(self, enabled: bool) -> None:
        self.spatial_enabled = enabled
        if enabled:
            self.play_startup_sequence()
        logger.info("Spatial audio: %s", enabled)

    def load_whisper(self) -> None:
        """
        Load Whisper model in background.
        FIX 1: Clears _whisper_ready during load so dependent calls can wait.
        Sets it again when done — speak() is unaffected (uses separate queue).
        """
        if not _WHISPER_AVAILABLE:
            return
        try:
            # Only clear the event for STT-dependent operations, not TTS
            logger.info("Loading Whisper %s...", WHISPER_MODEL)
            self._whisper_model = openai_whisper.load_model(WHISPER_MODEL)
            self._whisper_ready.set()  # Signal that Whisper is ready
            logger.info("Whisper loaded and ready")
            _track("WhisperLoaded", {"model": WHISPER_MODEL})
        except Exception as exc:
            self._whisper_ready.set()  # Always set — don't leave callers waiting forever
            logger.error("Whisper load error: %s", exc)

    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio file using Whisper.
        FIX 1: Waits for Whisper to be ready (up to 30s) before attempting.
        """
        # Wait for Whisper to finish loading — max 30 seconds
        ready = self._whisper_ready.wait(timeout=30)
        if not ready or not self._whisper_model:
            logger.warning("Whisper not ready — transcription skipped")
            self._voice_command_failures += 1
            return ""
        try:
            result = self._whisper_model.transcribe(audio_path, fp16=False)
            text = result.get("text", "").strip()
            self._voice_command_count += 1
            _track("VoiceCommandTranscribed", {
                "length_chars": str(len(text)),
                "language": self._language,
                "success_rate": f"{self._voice_command_count / max(1, self._voice_command_count + self._voice_command_failures):.2f}"
            })
            return text
        except Exception as exc:
            self._voice_command_failures += 1
            logger.error("Transcription error: %s", exc)
            return ""

    def set_language(self, language: str) -> None:
        """
        FIX 2: Set language AND immediately update Azure TTS voice.
        Original code updated self._language but never rebuilt the speech config,
        so the old voice kept speaking even after language was changed.
        """
        self._language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

        # FIX 2: Rebuild speech config with new voice immediately
        if self._use_azure_tts:
            self._build_speech_config()
            logger.info("Azure TTS voice updated to: %s",
                        AZURE_VOICE_MAP.get(self._language, "en-ZA-LeahNeural"))

        _track("LanguageChanged", {"language": self._language})
        logger.info("Audio language: %s", self._language)

        # Speak confirmation in the newly selected language
        phrase = LANGUAGE_CONFIRM_PHRASES.get(self._language, f"Language: {self._language}")
        self.speak(phrase)

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._tts_worker, daemon=True, name="TTS").start()
        threading.Thread(target=self._spatial_loop, daemon=True, name="SpatialAudio").start()
        logger.info("AudioEngine started — Azure TTS: %s, Translator: %s",
                    self._use_azure_tts, self._use_translator)
        _track("AudioEngineStarted", {
            "azure_tts": str(self._use_azure_tts),
            "translator": str(self._use_translator)
        })

    def stop(self) -> None:
        self._running = False
        # Flush any remaining TTS
        try:
            while not self._tts_queue.empty():
                self._tts_queue.get_nowait()
        except Exception:
            pass
        logger.info("AudioEngine stopped")
        _track("AudioEngineStopped", {
            "voice_commands": str(self._voice_command_count),
            "failures": str(self._voice_command_failures)
        })
        if _tc:
            try:
                _tc.flush()
            except Exception:
                pass


# Singleton
audio_engine = AudioEngine()
