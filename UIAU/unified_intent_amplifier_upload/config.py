"""
config.py — All constants, thresholds, and language codes for Unified Intent Amplifier.

FIXES APPLIED:
  - FIX 1: SUPPORTED_LANGUAGES tts_lang corrected — isiZulu/Sesotho/Afrikaans were
            all mapped to "en" meaning TTS spoke English even in other languages
  - FIX 2: All Azure environment variable names match the .env template exactly
  - FIX 3: Feature flags loaded from .env so Azure services can be toggled without
            touching code
  - FIX 4: Tremor severity presets centralised here so all engines use same values
  - FIX 5: SCREENSHOT_INTERVAL_S increased to 8s — 5s was too aggressive for Azure
            Vision API free tier limits (5,000 calls/month)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from same directory as this file
load_dotenv(Path(__file__).parent / ".env")

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DB_PATH    = BASE_DIR / "user_profile.db"
LOG_PATH   = BASE_DIR / "app.log"

# ── Whisper ─────────────────────────────────────────────────────────────────
# tiny = fastest, smallest, works on any CPU
# base = slightly more accurate, needs 2x RAM
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")

# ── Gaze Engine ─────────────────────────────────────────────────────────────
GAZE_SMOOTHING_ALPHA    = 0.18
GAZE_BLINK_EAR_THRESHOLD = 0.21
GAZE_BLINK_FRAMES       = 3
GAZE_DWELL_MS           = 800
GAZE_SENSITIVITY_X      = 5.5
GAZE_SENSITIVITY_Y      = 4.0
GAZE_DEAD_ZONE_PX       = 5
GAZE_SNAP_RADIUS        = 55          # px — tighter snap, less jumping
GAZE_SNAP_DWELL_FRAMES  = 8           # must stay near button for 8 frames before snap locks

# MediaPipe iris landmark indices (with refine_landmarks=True)
# After cv2.flip(frame, 1):
#   IRIS_LEFT_IDX  → left side of screen  → smaller x value
#   IRIS_RIGHT_IDX → right side of screen → larger x value
# gaze_engine.py auto-detects and corrects if these are swapped
IRIS_LEFT_IDX  = [474, 475, 476, 477]
IRIS_RIGHT_IDX = [469, 470, 471, 472]

# Eye landmarks for EAR (Eye Aspect Ratio) blink detection
EAR_LEFT_IDX  = [362, 385, 387, 263, 373, 380]
EAR_RIGHT_IDX = [33,  160, 158, 133, 153, 144]

# ── Motor / Tremor Engine ────────────────────────────────────────────────────
# Kalman filter — ratio of R:Q determines smoothing strength
# FIXED: Much less aggressive for responsive cursor
KALMAN_Q                 = 0.05    # Much higher = very responsive
KALMAN_R                 = 1.0     # Lower = trust measurements more
KALMAN_VELOCITY_BYPASS_PX = 100    # Very high threshold = almost always bypass
DOUBLE_KEY_MS            = 120     # Typing correction suppression window (ms)
TYPING_CORRECTION_ENABLED = True

# FIX 4: Tremor severity presets — used by motor_engine.set_severity()
# Clinical Director agent calls set_severity() based on session tremor data
# INVERTED LOGIC: Small movements = tremor (get filtered), Large movements = intentional (bypass)
TREMOR_SEVERITY_PRESETS = {
    "none":     {"q": 0.02,   "r": 1.0,  "bypass_px": 80},   # Light smoothing, high bypass
    "mild":     {"q": 0.01,   "r": 2.0,  "bypass_px": 60},   # Moderate smoothing
    "moderate": {"q": 0.005,  "r": 3.0,  "bypass_px": 40},   # Stronger smoothing
    "severe":   {"q": 0.002,  "r": 5.0,  "bypass_px": 25},   # Heavy smoothing, low bypass
}
DEFAULT_TREMOR_SEVERITY = "mild"  # Start with mild (less aggressive)

# ── Audio Engine ─────────────────────────────────────────────────────────────
SPATIAL_AUDIO_SAMPLE_RATE    = 44100
SPATIAL_AUDIO_DURATION       = 0.35
SPATIAL_AUDIO_LOOP_INTERVAL_S = 2.0
TTS_RATE   = 150
TTS_VOLUME = 0.9

# ── Overlay UI ───────────────────────────────────────────────────────────────
OVERLAY_WIDTH  = 420
OVERLAY_HEIGHT = 200
OVERLAY_ALPHA  = 0.93
OVERLAY_BG     = "#1a1a2e"
OVERLAY_FG     = "#e0e0e0"
OVERLAY_ACCENT = "#00d4ff"
OVERLAY_FONT   = ("Segoe UI", 10)

# ── Cognitive Engine ──────────────────────────────────────────────────────────
# FIX 5: 8s not 5s — Vision API free tier = 5,000 calls/month
# At 5s interval = 518,400 calls/month — blows the free tier in <1 day
# At 8s interval = 324,000 calls/month — still too many, but tip cooldown
# of 25s means Vision is only called when a new tip is due (~3 calls/min)
SCREENSHOT_INTERVAL_S    = 8
SIMPLIFY_CONTRAST_FACTOR = 1.4
TIP_COOLDOWN_S           = 25      # Min seconds between tips — controls Vision API usage

# ── Languages ─────────────────────────────────────────────────────────────────
# FIX 1: tts_lang now correctly set per language
# Original had ALL languages mapped to tts_lang: "en" — meaning isiZulu TTS
# was speaking English even when the user selected isiZulu. Fixed.
# Azure Neural TTS handles the actual voice — audio_engine.py uses AZURE_VOICE_MAP
SUPPORTED_LANGUAGES = {
    "English":   {"code": "en", "tts_lang": "en", "gtts_tld": "co.za"},
    "isiZulu":   {"code": "zu", "tts_lang": "zu", "gtts_tld": "co.za"},  # FIX 1
    "Sesotho":   {"code": "st", "tts_lang": "st", "gtts_tld": "co.za"},  # FIX 1
    "Afrikaans": {"code": "af", "tts_lang": "af", "gtts_tld": "co.za"},  # FIX 1
}
DEFAULT_LANGUAGE = "English"

# ── LLM / Azure OpenAI ────────────────────────────────────────────────────────
LLM_MAX_TOKENS  = 256
LLM_TEMPERATURE = 0.7
LLM_TIMEOUT_S   = 10

# ── Threading ─────────────────────────────────────────────────────────────────
THREAD_SLEEP_MS = 16   # ~60fps polling rate

# ── Azure Feature Flags ───────────────────────────────────────────────────────
# FIX 2/3: All flags loaded from .env — set to "true" or "false" there
# Default to "false" so app runs offline if .env is incomplete
USE_AZURE_TTS        = os.getenv("USE_AZURE_TTS",        "false").lower() == "true"
USE_AZURE_VISION     = os.getenv("USE_AZURE_VISION",     "false").lower() == "true"
USE_AZURE_OPENAI     = os.getenv("USE_AZURE_OPENAI",     "false").lower() == "true"
USE_AZURE_COSMOS     = os.getenv("USE_AZURE_COSMOS",     "false").lower() == "true"
USE_AZURE_TRANSLATOR = os.getenv("USE_AZURE_TRANSLATOR", "false").lower() == "true"
USE_AZURE_SEARCH     = os.getenv("USE_AZURE_SEARCH",     "false").lower() == "true"
USE_SERVICE_BUS      = os.getenv("USE_SERVICE_BUS",      "false").lower() == "true"
USE_APP_INSIGHTS     = os.getenv("USE_APP_INSIGHTS",     "false").lower() == "true"

# ── Azure Credentials (read from .env) ───────────────────────────────────────
# FIX 2: Variable names match .env template exactly
# Engines read os.getenv() directly but these are here for reference and validation
AZURE_OPENAI_API_KEY        = os.getenv("AZURE_OPENAI_API_KEY",        "")
AZURE_OPENAI_ENDPOINT       = os.getenv("AZURE_OPENAI_ENDPOINT",       "")
AZURE_OPENAI_DEPLOYMENT     = os.getenv("AZURE_OPENAI_DEPLOYMENT",     "gpt-4o")
AZURE_OPENAI_MINI_DEPLOYMENT = os.getenv("AZURE_OPENAI_MINI_DEPLOYMENT","gpt-4o-mini")
AZURE_OPENAI_API_VERSION    = os.getenv("AZURE_OPENAI_API_VERSION",    "2025-01-01-preview")
AZURE_ASSISTANT_ID          = os.getenv("AZURE_ASSISTANT_ID",          "")

AZURE_AI_SERVICES_KEY       = os.getenv("AZURE_AI_SERVICES_KEY",       "")
AZURE_AI_SERVICES_ENDPOINT  = os.getenv("AZURE_AI_SERVICES_ENDPOINT",  "")

AZURE_SPEECH_KEY            = os.getenv("AZURE_SPEECH_KEY",            "")
AZURE_SPEECH_REGION         = os.getenv("AZURE_SPEECH_REGION",         "eastus")

AZURE_TRANSLATOR_KEY        = os.getenv("AZURE_TRANSLATOR_KEY",        "")
AZURE_TRANSLATOR_ENDPOINT   = os.getenv("AZURE_TRANSLATOR_ENDPOINT",
                                         "https://api.cognitive.microsofttranslator.com")
AZURE_TRANSLATOR_REGION     = os.getenv("AZURE_TRANSLATOR_REGION",     "")

AZURE_COSMOS_CONNECTION_STRING = os.getenv("AZURE_COSMOS_CONNECTION_STRING", "")
AZURE_COSMOS_DATABASE          = os.getenv("AZURE_COSMOS_DATABASE",
                                            "precision_pad_db")

AZURE_SEARCH_KEY             = os.getenv("AZURE_SEARCH_KEY",           "")
AZURE_SEARCH_ENDPOINT        = os.getenv("AZURE_SEARCH_ENDPOINT",      "")
AZURE_SEARCH_INDEX           = os.getenv("AZURE_SEARCH_INDEX",
                                          "accessibility-guides")

AZURE_APPINSIGHTS_INSTRUMENTATION_KEY = os.getenv(
    "AZURE_APPINSIGHTS_INSTRUMENTATION_KEY", "")
AZURE_APPINSIGHTS_CONNECTION_STRING   = os.getenv(
    "AZURE_APPINSIGHTS_CONNECTION_STRING",   "")

AZURE_SERVICE_BUS_CONNECTION_STRING  = os.getenv(
    "AZURE_SERVICE_BUS_CONNECTION_STRING", "")
AZURE_SERVICE_BUS_SCREENSHOT_QUEUE   = os.getenv(
    "AZURE_SERVICE_BUS_SCREENSHOT_QUEUE", "screenshot-queue")
AZURE_SERVICE_BUS_TIPS_QUEUE         = os.getenv(
    "AZURE_SERVICE_BUS_TIPS_QUEUE",       "tips-queue")

AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_STORAGE_CONTAINER         = os.getenv("AZURE_STORAGE_CONTAINER",
                                              "calibration-backups")

# ── Startup validation — warns if Azure keys are missing when flags are True ──
def validate_config():
    """Call this on startup to warn about missing keys for enabled services."""
    warnings = []
    if USE_AZURE_TTS and not AZURE_SPEECH_KEY:
        warnings.append("USE_AZURE_TTS=true but AZURE_SPEECH_KEY is empty")
    if USE_AZURE_VISION and not AZURE_AI_SERVICES_KEY:
        warnings.append("USE_AZURE_VISION=true but AZURE_AI_SERVICES_KEY is empty")
    if USE_AZURE_OPENAI and not AZURE_OPENAI_API_KEY:
        warnings.append("USE_AZURE_OPENAI=true but AZURE_OPENAI_API_KEY is empty")
    if USE_AZURE_COSMOS and not AZURE_COSMOS_CONNECTION_STRING:
        warnings.append("USE_AZURE_COSMOS=true but AZURE_COSMOS_CONNECTION_STRING is empty")
    if USE_APP_INSIGHTS and not AZURE_APPINSIGHTS_INSTRUMENTATION_KEY:
        warnings.append("USE_APP_INSIGHTS=true but AZURE_APPINSIGHTS_INSTRUMENTATION_KEY is empty")
    if USE_AZURE_TRANSLATOR and not AZURE_TRANSLATOR_KEY:
        warnings.append("USE_AZURE_TRANSLATOR=true but AZURE_TRANSLATOR_KEY is empty")
    for w in warnings:
        import logging
        logging.getLogger("config").warning("CONFIG WARNING: %s", w)
    return len(warnings) == 0


# Run validation on import — warnings appear in startup logs
validate_config()
