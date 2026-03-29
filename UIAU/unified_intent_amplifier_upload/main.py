"""
main.py — Unified Intent Amplifier entry point.

FIXES APPLIED:
  - FIX 1: atexit.register(tray.stop) — tray icon always removed on exit/crash
  - FIX 2: cognitive_engine fully wired — was imported in other files but never
            started or connected to overlay/audio in main.py
  - FIX 3: Employment Mode callback wired to overlay
  - FIX 4: Gaze blink confirmation callback wired to overlay
  - FIX 5: App Insights startup event — shows active user on demo dashboard
  - FIX 6: Cosmos DB profile sync on startup
  - FIX 7: Log file added alongside stdout so errors are captured after demo
"""

import os
import sys
import logging
import threading
import atexit
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

# FIX 7: Log to both stdout AND a file — captures errors even after demo
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            Path(__file__).parent / "app.log",
            encoding="utf-8",
            mode="a"
        ),
    ],
)
logger = logging.getLogger("main")

# ── App Insights startup telemetry ──────────────────────────────────────────
_tc = None
if os.getenv("USE_APP_INSIGHTS", "false").lower() == "true":
    try:
        from applicationinsights import TelemetryClient
        _tc = TelemetryClient(os.getenv("AZURE_APPINSIGHTS_INSTRUMENTATION_KEY", ""))
    except ImportError:
        logger.warning("applicationinsights not installed — pip install applicationinsights")

def _track(event: str, props: dict = None):
    if _tc:
        try:
            _tc.track_event(event, props or {})
            _tc.flush()
        except Exception:
            pass

# ── Engine imports ──────────────────────────────────────────────────────────
from user_profile import init_db
from gaze_engine import gaze_engine
from motor_engine import motor_engine
from audio_engine import audio_engine
from spatial_audio import spatial_audio
from ai_assistant import ai_assistant
from cognitive_engine import cognitive_engine   # FIX 2: was never imported in original
from agent_vision import screen_agent
from agent_team import agent_team
from overlay import OverlayWindow
from tray_app import TrayApp
from ui_automation import ui_automation
from voice_nav import voice_nav


def main():
    logger.info("=" * 60)
    logger.info("  Unified Intent Amplifier — Starting")
    logger.info("=" * 60)

    # FIX 5: Track app startup in App Insights — shows on demo dashboard immediately
    _track("AppStarted", {
        "azure_tts":     os.getenv("USE_AZURE_TTS", "false"),
        "azure_vision":  os.getenv("USE_AZURE_VISION", "false"),
        "azure_openai":  os.getenv("USE_AZURE_OPENAI", "false"),
        "azure_cosmos":  os.getenv("USE_AZURE_COSMOS", "false"),
        "version":       "2.0.0",
    })

    # ── Database init ───────────────────────────────────────────────────────
    init_db()

    # FIX 6: Sync Cosmos DB profile on startup (non-blocking)
    def _sync_cosmos():
        if os.getenv("USE_AZURE_COSMOS", "false").lower() != "true":
            return
        try:
            from azure.cosmos import CosmosClient
            conn_str = os.getenv("AZURE_COSMOS_CONNECTION_STRING", "")
            if not conn_str:
                return
            client = CosmosClient.from_connection_string(conn_str)
            db = client.create_database_if_not_exists(
                os.getenv("AZURE_COSMOS_DATABASE", "precision_pad_db")
            )
            for container_name in ["users", "sessions", "tips_feedback", "site_guides"]:
                db.create_container_if_not_exists(
                    id=container_name,
                    partition_key={"kind": "Hash", "paths": ["/id"]}
                )
            logger.info("Cosmos DB containers verified")
            _track("CosmosDBConnected")
        except Exception as exc:
            logger.warning("Cosmos DB sync failed (offline mode): %s", exc)
    threading.Thread(target=_sync_cosmos, daemon=True, name="CosmosSync").start()

    # ── Overlay ─────────────────────────────────────────────────────────────
    overlay = OverlayWindow()

    # ── Start all engines ───────────────────────────────────────────────────
    motor_engine.start()
    motor_engine.set_typing(True)
    gaze_engine.start()
    audio_engine.start()
    spatial_audio.start()

    # FIX 2: Start cognitive engine — was never started in original main.py
    cognitive_engine.start()

    # ── Screen Understanding Agent ───────────────────────────────────────────
    screen_agent.on_tip = overlay.show_tip
    screen_agent.on_speak = audio_engine.speak
    screen_agent.start()
    screen_agent.set_enabled(True)

    # ── UI Automation (magnetic snap + form filling) ────────────────────────
    ui_automation.on_tip       = overlay.show_tip
    ui_automation.on_snap_audio = spatial_audio.play_cue_at_position
    ui_automation.start()

    # ── Multi-Agent Team ───────────────────────────────────────────────────────
    agent_team.on_tip = overlay.show_tip
    agent_team.on_speak = audio_engine.speak
    agent_team.ui_automation = ui_automation
    agent_team.set_screen_agent(screen_agent)

    # ── AI Assistant ─────────────────────────────────────────────────────────
    ai_assistant.on_tip   = overlay.show_tip
    ai_assistant.on_speak = audio_engine.speak
    ai_assistant.start()

    # ── Wire cognitive engine to overlay and audio ───────────────────────────
    # FIX 2: cognitive_engine callbacks were never connected
    cognitive_engine.on_tip_callback    = overlay.show_tip
    cognitive_engine.on_speak_callback  = audio_engine.speak

    # FIX 3: Employment Mode — overlay switches UI when job site detected
    def _on_employment_mode(site: str):
        overlay.show_tip(f"💼 Employment Mode: {site.upper()} detected")
        logger.info("Employment Mode activated for site: %s", site)
        _track("EmploymentModeUI", {"site": site})
    cognitive_engine.on_employment_mode_callback = _on_employment_mode

    # FIX 4: Gaze blink confirmation — overlay shows/hides confirm prompt
    def _on_blink_confirm(show: bool):
        if show:
            overlay.show_tip("👁 Blink again to confirm click")
        else:
            overlay.show_tip("")
    gaze_engine.on_confirm_callback = _on_blink_confirm

    # ── Wire overlay toggles ─────────────────────────────────────────────────
    overlay.on_toggle["gaze"]      = gaze_engine.set_enabled
    overlay.on_toggle["tremor"]    = motor_engine.set_tremor
    overlay.on_toggle["typing"]    = motor_engine.set_typing
    overlay.on_toggle["audio"]     = spatial_audio.set_enabled
    overlay.on_toggle["cognitive"] = cognitive_engine.set_enabled  # FIX 2

    # ── Language switcher ────────────────────────────────────────────────────
    def _on_language(lang: str):
        audio_engine.set_language(lang)
        ai_assistant.set_language(lang)
        cognitive_engine.set_language(lang)  # FIX 2: was missing
        _track("LanguageSwitched", {"language": lang})
    overlay.on_language = _on_language

    # ── AI Assist / Read Screen Now ──────────────────────────────────────────
    overlay.on_cognitive   = cognitive_engine.set_enabled   # FIX 2: was ai_assistant
    overlay.on_read_screen = cognitive_engine.read_screen_now  # FIX 2: was ai_assistant
    overlay.on_ask_voice        = cognitive_engine.answer_question  # ChatGPT-style Q&A
    overlay.on_ask_voice_record = ai_assistant.record_question  # NEW: mic → text transcription
    overlay.on_ideas = lambda: agent_team.run_async(
        "I am not sure what to do next. Give me 3 ideas.")

    # ── Tray ─────────────────────────────────────────────────────────────────
    tray = TrayApp(overlay=overlay)
    tray.start()

    # FIX 1: Register tray cleanup with atexit — tray icon removed even on crash
    atexit.register(tray.stop)

    # ── Voice Navigation (F4 push-to-talk) ──────────────────────────────────
    voice_nav.ui_automation     = ui_automation
    voice_nav.cognitive_engine  = cognitive_engine
    voice_nav.ai_assistant      = ai_assistant
    voice_nav.on_tip           = overlay.show_tip
    voice_nav.on_speak         = audio_engine.speak
    voice_nav.on_listening_start = lambda: overlay.show_tip("🎤 Listening...")
    voice_nav.on_listening_stop  = lambda: overlay.show_tip("")

    # ── Load Whisper in background ───────────────────────────────────────────
    def _load_whisper():
        audio_engine.load_whisper()
        ai_assistant.set_whisper(audio_engine._whisper_model)
        voice_nav.start(whisper_model=audio_engine._whisper_model)
        logger.info("Whisper ready — voice commands active (hold F4 to speak)")
        _track("WhisperReady", {"model": os.getenv("WHISPER_MODEL", "tiny")})
    threading.Thread(target=_load_whisper, daemon=True, name="WhisperLoader").start()

    # ── Ready ────────────────────────────────────────────────────────────────
    logger.info("All engines started.")
    audio_engine.speak("Unified Intent Amplifier is ready.")
    _track("AppReady")

    # ── Main loop ────────────────────────────────────────────────────────────
    try:
        overlay.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt — shutting down")
    except Exception as exc:
        logger.error("Unexpected error in main loop: %s", exc, exc_info=True)
        _track("AppCrash", {"error": str(exc)})
    finally:
        logger.info("Shutting down all engines...")
        _track("AppStopped")
        if _tc:
            try:
                _tc.flush()
            except Exception:
                pass
        voice_nav.stop()
        ui_automation.stop()
        cognitive_engine.stop()   # FIX 2
        screen_agent.stop()
        gaze_engine.stop()
        motor_engine.stop()
        audio_engine.stop()
        spatial_audio.stop()
        ai_assistant.stop()
        tray.stop()               # FIX 1: also called by atexit as backup
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
