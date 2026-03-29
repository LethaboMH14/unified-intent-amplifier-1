"""
=============================================================
ISAZI AI ACCESSIBILITY HACKATHON
Phase 2 — Build Crew
Unified Intent Amplifier
Azure OpenAI GPT-4o Edition
=============================================================
9 agents. Hierarchical process.
Input:  project_brief.md (from Phase 1)
Output: Complete working Python application

ARCHITECTURE:
  UI:       System tray app (pystray) + always-on-top overlay (tkinter)
  Priority: 1. Gaze/eye control  2. Tremor+typing  3. Cognitive  4. Multilingual

AGENTS:
  Manager     — CTO, coordinates all 8 specialists
  Architect   — system design, module structure, threading model
  Gaze        — MediaPipe eye/blink tracking → mouse replacement
  Motor       — Kalman tremor filter + pynput typing correction
  Overlay     — tkinter overlay + pystray tray icon + UI
  Cognitive   — screen simplification + task coaching
  Multilingual— pyttsx3/gTTS voice in EN/ZU/ST/AF
  QA          — integration tests + demo script verification
  Demo        — final video script + submission checklist

RUN:
  python phase2_build.py
=============================================================
"""

import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool

load_dotenv()

AZURE_API_KEY     = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT    = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_DEPLOYMENT  = os.getenv("AZURE_OPENAI_DEPLOYMENT")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

for var, val in [
    ("AZURE_OPENAI_API_KEY",    AZURE_API_KEY),
    ("AZURE_OPENAI_ENDPOINT",   AZURE_ENDPOINT),
    ("AZURE_OPENAI_DEPLOYMENT", AZURE_DEPLOYMENT),
]:
    if not val:
        raise ValueError(f"\n  Missing: {var}\n  Add to .env and retry.\n")

llm_manager = LLM(
    model=f"azure/{AZURE_DEPLOYMENT}",
    api_key=AZURE_API_KEY,
    base_url=AZURE_ENDPOINT,
    api_version=AZURE_API_VERSION,
    temperature=0.2,
    max_tokens=4096,
)

llm_builder = LLM(
    model=f"azure/{AZURE_DEPLOYMENT}",
    api_key=AZURE_API_KEY,
    base_url=AZURE_ENDPOINT,
    api_version=AZURE_API_VERSION,
    temperature=0.1,   # low — we want precise, runnable code
    max_tokens=8096,
)

llm_creative = LLM(
    model=f"azure/{AZURE_DEPLOYMENT}",
    api_key=AZURE_API_KEY,
    base_url=AZURE_ENDPOINT,
    api_version=AZURE_API_VERSION,
    temperature=0.4,
    max_tokens=4096,
)

search_tool = SerperDevTool(
    api_key=os.getenv("SERPER_API_KEY"),
    n_results=5,
)

# ─────────────────────────────────────────────────────────
# READ THE PROJECT BRIEF
# ─────────────────────────────────────────────────────────
try:
    with open("project_brief.md", "r", encoding="utf-8") as f:
        PROJECT_BRIEF = f.read()
    print("  ✓ project_brief.md loaded successfully")
except FileNotFoundError:
    raise FileNotFoundError(
        "\n  project_brief.md not found!\n"
        "  Run phase1_brainstorm_v2.py first to generate it.\n"
    )

# ─────────────────────────────────────────────────────────
# BUILD CONTEXT — injected into every agent
# ─────────────────────────────────────────────────────────
BUILD_CONTEXT = f"""
=== PROJECT BRIEF (SOURCE OF TRUTH) ===
{PROJECT_BRIEF}

=== BUILD DECISIONS (LOCKED) ===
APP NAME         : Unified Intent Amplifier
UI ARCHITECTURE  : System tray app (pystray) + always-on-top tkinter overlay
DEMO PRIORITY    : 1. Gaze/eye control  2. Tremor+typing  3. Cognitive  4. Multilingual
LIVE DEMO FEATURES (ALL MUST WORK): Gaze control, Spatial audio, Tremor smoothing, Typing correction
PLATFORM         : Windows laptop (primary), Python 3.11
LLM              : Azure OpenAI GPT-4o via LangChain AzureChatOpenAI
OFFLINE          : All 4 demo features must work with zero internet
BUILD TIME       : 72 hours

=== TECH STACK (LOCKED) ===
Gaze tracking    : mediapipe==0.10.9 (FaceMesh, iris landmarks 468-473)
Tremor filter    : numpy Kalman filter — Q=0.01, R=0.1 (custom, no extra lib)
Keyboard hook    : pynput==1.7.6
Mouse control    : pyautogui==0.9.54 + pynput for raw coords
Voice STT        : openai-whisper (whisper-tiny, CPU-only, offline)
TTS              : pyttsx3==2.90 (offline) + gTTS (online fallback)
Overlay UI       : tkinter (stdlib) — always-on-top transparent window
Tray app         : pystray==0.19.5 + Pillow==10.3.0
Screen capture   : pyautogui screenshot for cognitive overlay
Database         : sqlite3 (stdlib) — user profiles
Config           : python-dotenv==1.1.1
LLM integration  : langchain-openai (AzureChatOpenAI) for coaching prompts

=== FILE STRUCTURE (BUILD TO THIS EXACTLY) ===
unified_intent_amplifier/
├── main.py                  # entry point — starts tray + overlay threads
├── tray_app.py              # pystray system tray, menu, toggle controls
├── overlay.py               # tkinter always-on-top overlay window
├── gaze_engine.py           # MediaPipe iris tracking → virtual mouse
├── motor_engine.py          # Kalman tremor filter + pynput typing correction
├── audio_engine.py          # whisper STT + pyttsx3 TTS + spatial audio
├── cognitive_engine.py      # screen simplification + task coaching
├── llm_coach.py             # AzureChatOpenAI — adaptive coaching prompts
├── user_profile.py          # SQLite profile — learns user over time
├── config.py                # all constants, thresholds, language codes
├── requirements.txt         # pinned versions
└── README.md                # setup + run instructions

=== CODING STANDARDS ===
- Every file must be immediately runnable — no pseudocode, no placeholders
- Every function must have a docstring
- All thresholds in config.py — never hardcoded in engine files
- Threading: each engine runs in its own daemon thread
- Graceful degradation: if webcam unavailable, gaze engine sleeps silently
- All user data stored locally only — never sent anywhere
- Windows-compatible paths (use pathlib.Path throughout)
"""


# ═══════════════════════════════════════════════════════════
# AGENT 1 — SYSTEM ARCHITECT
# Designs the threading model and module contracts
# ═══════════════════════════════════════════════════════════
agent_architect = Agent(
    role="Senior Python Systems Architect",
    goal=(
        "Design the complete system architecture for Unified Intent Amplifier — "
        "threading model, inter-module communication, startup sequence, and "
        "the exact API contract each module must expose."
    ),
    backstory=(
        "You are a principal Python engineer who has shipped real-time desktop "
        "applications. You know that multi-threaded Python with tkinter is a minefield "
        "if you don't get the threading model right on day one. You know that tkinter "
        "must run on the main thread. You know that MediaPipe can't share a cv2 "
        "VideoCapture across threads. You know that pynput keyboard hooks on Windows "
        "need a separate thread with its own event loop. "
        "You design clean module contracts with queues for inter-thread communication "
        "so every specialist engineer knows exactly what their module receives and emits. "
        "You write the architecture document that prevents all the 3am integration bugs."
    ),
    tools=[],
    llm=llm_manager,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_architect = Task(
    description=(
        f"{BUILD_CONTEXT}\n\n"
        "YOUR TASK: Design the complete system architecture.\n\n"
        "DELIVER:\n\n"
        "1. THREADING MODEL\n"
        "   - Main thread: what runs here (tkinter overlay — mandatory)\n"
        "   - Thread 2: gaze_engine (cv2 + MediaPipe loop)\n"
        "   - Thread 3: motor_engine (pynput keyboard/mouse hooks)\n"
        "   - Thread 4: audio_engine (whisper inference loop)\n"
        "   - Thread 5: cognitive_engine (screen analysis loop)\n"
        "   - How threads communicate: queue.Queue objects — name each queue\n"
        "   - Shutdown sequence: how all threads stop cleanly\n\n"
        "2. MODULE CONTRACTS (for each of the 8 modules)\n"
        "   - Input: what it receives (queue name + data type)\n"
        "   - Output: what it emits (queue name + data type)\n"
        "   - Public API: function signatures the other modules call\n"
        "   - Failure mode: what happens if the sensor is unavailable\n\n"
        "3. STARTUP SEQUENCE\n"
        "   - Exact order main.py starts each component\n"
        "   - Which components are mandatory vs optional\n"
        "   - How the tray icon appears before all engines are ready\n\n"
        "4. config.py COMPLETE CONTENTS\n"
        "   Write the FULL config.py file with every constant:\n"
        "   - Kalman filter params (Q, R, initial state)\n"
        "   - MediaPipe confidence thresholds\n"
        "   - Blink detection threshold (EAR ratio)\n"
        "   - Gaze dwell time for click (milliseconds)\n"
        "   - Typing correction params (double-key window ms, tremor window ms)\n"
        "   - Overlay dimensions and opacity\n"
        "   - Language codes dict\n"
        "   - SQLite db path\n"
        "   - All feature toggle flags\n\n"
        "5. main.py COMPLETE CODE\n"
        "   Write the full main.py that wires everything together.\n"
    ),
    expected_output=(
        "Complete threading model. Module contracts for all 8 modules. "
        "Startup sequence. Full config.py code. Full main.py code."
    ),
    agent=agent_architect,
)


# ═══════════════════════════════════════════════════════════
# AGENT 2 — GAZE ENGINE ENGINEER
# Builds the eye/blink tracking → virtual mouse
# This is priority #1 for the demo
# ═══════════════════════════════════════════════════════════
agent_gaze = Agent(
    role="Computer Vision and Gaze Tracking Engineer",
    goal=(
        "Build gaze_engine.py — the complete MediaPipe iris tracking system "
        "that turns eye gaze into mouse movement and blinks into clicks, "
        "working reliably on a standard laptop webcam with no special hardware."
    ),
    backstory=(
        "You have shipped eye-tracking systems using only webcams. "
        "You know MediaPipe FaceMesh gives 478 landmarks — the iris landmarks "
        "are 468-471 (left) and 473-477 (right). You know the Eye Aspect Ratio "
        "(EAR) formula for blink detection: EAR = (|p2-p6| + |p3-p5|) / (2|p1-p4|). "
        "You know that raw gaze vectors drift and need exponential smoothing "
        "with alpha=0.3 before mapping to screen coordinates. "
        "You know the dwell-click pattern: user gazes at a target for N milliseconds "
        "→ click fires — and you know N must be configurable because locked-in users "
        "need longer dwell times than users who just have tremors. "
        "You know that gaze fatigue sets in and the system must detect when "
        "blink rate drops (fatigue signal) and offer to switch input mode. "
        "You write clean, commented, immediately runnable Python."
    ),
    tools=[search_tool],
    llm=llm_builder,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_gaze = Task(
    description=(
        f"{BUILD_CONTEXT}\n\n"
        "YOUR TASK: Write the complete gaze_engine.py file.\n\n"
        "MUST IMPLEMENT:\n\n"
        "1. IRIS TRACKING\n"
        "   - MediaPipe FaceMesh with refine_landmarks=True (required for iris)\n"
        "   - Extract iris center from landmarks 468-471 (left) and 473-477 (right)\n"
        "   - Map normalized iris position to screen pixel coordinates\n"
        "   - Exponential moving average smoothing: alpha=0.3 (from config.py)\n"
        "   - Move actual mouse cursor using pyautogui.moveTo()\n\n"
        "2. BLINK DETECTION (click replacement)\n"
        "   - Eye Aspect Ratio (EAR) calculation using facial landmarks\n"
        "   - EAR threshold from config.py (default 0.21)\n"
        "   - Dwell-click: gaze held at same position for DWELL_MS → left click\n"
        "   - Long blink (>500ms) → right click\n"
        "   - Double blink (<300ms apart) → double click\n"
        "   - Anti-tremor: ignore blinks during active gaze movement\n\n"
        "3. FATIGUE DETECTION\n"
        "   - Track blink rate over 60-second rolling window\n"
        "   - If blink rate drops below 8/min → emit fatigue warning to overlay queue\n"
        "   - Suggest switching to voice input via audio_engine\n\n"
        "4. USER PROFILE LEARNING\n"
        "   - Save baseline EAR per user (first 2 minutes of use)\n"
        "   - Adjust EAR threshold dynamically based on user's baseline\n"
        "   - Store in user_profile.py\n\n"
        "5. GRACEFUL FAILURE\n"
        "   - If webcam not available: log warning, set GAZE_ACTIVE=False, return\n"
        "   - If face not detected for >3 seconds: emit status to overlay\n"
        "   - If lighting too dark (mean frame brightness <30): emit warning\n\n"
        "6. THREADING\n"
        "   - Run in daemon thread\n"
        "   - Accept stop_event: threading.Event to shut down cleanly\n"
        "   - Emit to gaze_queue: Queue({'x': int, 'y': int, 'blink': bool, 'status': str})\n\n"
        "Write the COMPLETE gaze_engine.py — every function, every import, "
        "every line. No pseudocode. No TODO comments. Runnable immediately.\n"
    ),
    expected_output="Complete, immediately runnable gaze_engine.py with all features implemented.",
    agent=agent_gaze,
    context=[task_architect],
)


# ═══════════════════════════════════════════════════════════
# AGENT 3 — MOTOR ENGINE ENGINEER
# Builds tremor filter + typing correction
# Priority #2 for the demo
# ═══════════════════════════════════════════════════════════
agent_motor = Agent(
    role="Motor Compensation and Keyboard Correction Engineer",
    goal=(
        "Build motor_engine.py — the Kalman filter tremor compensation system "
        "and the pynput keyboard hook that silently corrects double-typing, "
        "missed keys, and tremor-induced errors in real time."
    ),
    backstory=(
        "You have built assistive input systems for people with Parkinson's and "
        "cerebral palsy. You know the difference: Parkinson's tremor is rhythmic "
        "at 4-6Hz — a bandpass filter kills it cleanly. Cerebral palsy causes "
        "non-rhythmic spasms — you need intent detection, not filtering. "
        "For the mouse, you use a discrete Kalman filter on X,Y coordinates: "
        "predict the intended position, not the measured one. "
        "For the keyboard, you intercept every keystroke before the OS sees it "
        "using pynput, and you apply: "
        "(1) double-key suppression: if same key fires twice within 80ms, drop the second "
        "(2) key-hold filtering: if a key is held >400ms unintentionally, cap it "
        "(3) adjacent-key correction: 'tthe' → 'the', using a sliding window "
        "You learn each user's specific error patterns within 10 minutes and "
        "adjust thresholds automatically. The user never sees the correction — "
        "it happens before the OS registers the keystroke."
    ),
    tools=[search_tool],
    llm=llm_builder,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_motor = Task(
    description=(
        f"{BUILD_CONTEXT}\n\n"
        "YOUR TASK: Write the complete motor_engine.py file.\n\n"
        "MUST IMPLEMENT:\n\n"
        "1. KALMAN FILTER FOR MOUSE TREMOR\n"
        "   - Discrete Kalman filter using numpy only (no scipy, no filterpy)\n"
        "   - State vector: [x, y, dx, dy] (position + velocity)\n"
        "   - Process noise Q=0.01, measurement noise R=0.1 (from config.py)\n"
        "   - Hook raw mouse events via pynput.mouse.Listener\n"
        "   - Apply filter → move cursor to filtered position via pyautogui\n"
        "   - Bypass filter for fast intentional movements (velocity threshold)\n"
        "   - Intensity slider: 0=off, 1=light, 2=medium, 3=strong (from config)\n\n"
        "2. KEYBOARD TREMOR CORRECTION\n"
        "   - pynput.keyboard.Listener to intercept all keystrokes\n"
        "   - Double-key suppression: same key within DOUBLE_KEY_MS (80ms) → suppress\n"
        "   - Key-hold cap: key held beyond HOLD_CAP_MS (400ms) → emit single key\n"
        "   - Adjacent-key correction: sliding 4-char window → common SA English corrections\n"
        "   - Suppress the raw keystroke, emit corrected via pynput.keyboard.Controller\n\n"
        "3. USER LEARNING LOOP\n"
        "   - Track per-key error rate in rolling 100-keystroke window\n"
        "   - Adjust DOUBLE_KEY_MS threshold per user (range 50-200ms)\n"
        "   - Save learned thresholds to user_profile.py every 5 minutes\n"
        "   - Load saved profile on startup\n\n"
        "4. PARKINSON'S vs CEREBRAL PALSY MODE\n"
        "   - PARKINSONS_MODE: apply Kalman filter (rhythmic tremor)\n"
        "   - CP_MODE: apply velocity-based intent detection (non-rhythmic)\n"
        "   - AUTO_MODE: detect pattern automatically after 5 minutes\n"
        "   - Toggled from tray menu\n\n"
        "5. THREADING\n"
        "   - Run keyboard and mouse listeners in daemon threads\n"
        "   - Accept stop_event: threading.Event\n"
        "   - Emit stats to motor_queue: Queue({'corrections': int, 'mode': str})\n\n"
        "Write the COMPLETE motor_engine.py. Every line. Runnable immediately.\n"
    ),
    expected_output="Complete, immediately runnable motor_engine.py with Kalman filter and keyboard correction.",
    agent=agent_motor,
    context=[task_architect],
)


# ═══════════════════════════════════════════════════════════
# AGENT 4 — OVERLAY + TRAY UI ENGINEER
# Builds the visible interface: tray icon + overlay
# ═══════════════════════════════════════════════════════════
agent_overlay = Agent(
    role="Desktop UI and Overlay Engineer",
    goal=(
        "Build overlay.py and tray_app.py — the always-on-top transparent tkinter "
        "overlay and the pystray system tray app that together form the user interface "
        "of the Unified Intent Amplifier."
    ),
    backstory=(
        "You have built always-on-top overlay applications in Python. You know the "
        "tkinter tricks: overrideredirect(True) removes the title bar, "
        "attributes('-topmost', True) keeps it above everything, "
        "attributes('-alpha', 0.85) gives transparency, "
        "wm_attributes('-transparentcolor', 'black') on Windows makes black pixels "
        "invisible so the overlay doesn't block the screen. "
        "You know pystray: you create an Icon with a PIL Image and a Menu, "
        "run it in a daemon thread, and it sits in the system tray until dismissed. "
        "You design the overlay to show: current mode indicator, active feature status, "
        "correction count, fatigue warnings — all in a small semi-transparent corner HUD. "
        "The user can toggle individual features from the tray menu without touching "
        "the keyboard or mouse — important for users who can barely use either."
    ),
    tools=[],
    llm=llm_builder,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_overlay = Task(
    description=(
        f"{BUILD_CONTEXT}\n\n"
        "YOUR TASK: Write the complete overlay.py and tray_app.py files.\n\n"
        "overlay.py MUST IMPLEMENT:\n\n"
        "1. ALWAYS-ON-TOP TRANSPARENT HUD\n"
        "   - tkinter window: overrideredirect(True), topmost, alpha=0.85\n"
        "   - Position: bottom-right corner, 280x200px\n"
        "   - Black background with transparentcolor so bg is invisible\n"
        "   - Shows: app name + version, active features (green/grey dots), \n"
        "     corrections counter, current input mode, fatigue warning if triggered\n"
        "   - Smooth fade-in on startup (alpha 0→0.85 over 500ms)\n\n"
        "2. NOTIFICATION SYSTEM\n"
        "   - show_notification(message, level) — levels: INFO, WARN, SUCCESS\n"
        "   - Notification appears in overlay for 3 seconds then fades\n"
        "   - Color coded: INFO=white, WARN=amber, SUCCESS=green\n\n"
        "3. QUEUE LISTENER\n"
        "   - Reads from overlay_queue every 100ms\n"
        "   - Updates HUD labels in response to engine status messages\n"
        "   - Thread-safe (uses tkinter.after() not direct widget access)\n\n"
        "tray_app.py MUST IMPLEMENT:\n\n"
        "4. SYSTEM TRAY ICON\n"
        "   - pystray Icon with a simple PIL-drawn icon (blue circle with 'UIA')\n"
        "   - Menu items:\n"
        "     * 'Unified Intent Amplifier' (title, disabled)\n"
        "     * --- separator ---\n"
        "     * Toggle Gaze Control (checkable)\n"
        "     * Toggle Tremor Smoothing (checkable)\n"
        "     * Toggle Typing Correction (checkable)\n"
        "     * Toggle Spatial Audio (checkable)\n"
        "     * Toggle Cognitive Mode (checkable)\n"
        "     * --- separator ---\n"
        "     * Language: English / isiZulu / Sesotho / Afrikaans (radio)\n"
        "     * --- separator ---\n"
        "     * View Profile Stats\n"
        "     * Reset Profile\n"
        "     * --- separator ---\n"
        "     * Quit\n"
        "   - All toggles emit to control_queue for engines to read\n"
        "   - Runs in daemon thread\n\n"
        "Write COMPLETE overlay.py and tray_app.py. Every line. Runnable immediately.\n"
    ),
    expected_output="Complete overlay.py and tray_app.py — runnable immediately.",
    agent=agent_overlay,
    context=[task_architect],
)


# ═══════════════════════════════════════════════════════════
# AGENT 5 — AUDIO ENGINE ENGINEER
# Builds spatial audio navigation + whisper STT + pyttsx3 TTS
# ═══════════════════════════════════════════════════════════
agent_audio = Agent(
    role="Audio and Speech Processing Engineer",
    goal=(
        "Build audio_engine.py — the complete audio system including whisper offline "
        "speech-to-text, pyttsx3 multilingual text-to-speech, and spatial audio "
        "navigation that guides blind users through the screen using sound."
    ),
    backstory=(
        "You have built audio interfaces for blind users. You understand spatial audio: "
        "if the cursor is top-left, the audio cue pans left and pitches high. "
        "If it's bottom-right, it pans right and pitches low. "
        "You use pyttsx3 for offline TTS with language switching via voice IDs. "
        "You know whisper-tiny runs at ~0.3x realtime on CPU — fast enough for "
        "a 5-second voice command. You use sounddevice for audio capture and "
        "numpy for audio processing. "
        "For spatial audio, you generate stereo tones using numpy and play them "
        "via sounddevice — no external spatial audio library needed. "
        "You support EN/ZU/ST/AF by switching pyttsx3 voice and gTTS language code. "
        "Every spoken notification is also shown in the overlay — deaf users get "
        "the text, blind users get the audio."
    ),
    tools=[search_tool],
    llm=llm_builder,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_audio = Task(
    description=(
        f"{BUILD_CONTEXT}\n\n"
        "YOUR TASK: Write the complete audio_engine.py file.\n\n"
        "MUST IMPLEMENT:\n\n"
        "1. SPATIAL AUDIO NAVIGATION\n"
        "   - Generate stereo tone using numpy: freq maps to Y position (high=top)\n"
        "   - Pan maps to X position (left=left channel, right=right channel)\n"
        "   - Play via sounddevice.play() — non-blocking\n"
        "   - speak_element(element_name, x, y): announces UI element with spatial cue\n"
        "   - cursor_audio_mode(): continuous soft spatial tone follows gaze cursor\n\n"
        "2. WHISPER OFFLINE STT\n"
        "   - Load whisper.load_model('tiny') on startup (CPU only)\n"
        "   - Record audio: sounddevice.rec() for 5 seconds on voice trigger\n"
        "   - Transcribe offline: whisper.transcribe(audio, language='en')\n"
        "   - Language-aware: switch whisper language based on active language setting\n"
        "   - Voice command parser: map common commands to actions\n"
        "     'scroll down', 'click', 'go back', 'open email', 'read screen'\n"
        "   - Emit commands to control_queue\n\n"
        "3. PYTTSX3 MULTILINGUAL TTS\n"
        "   - Init pyttsx3 engine on startup\n"
        "   - speak(text, lang='en'): speaks text in specified language\n"
        "   - Language voices: EN=default, ZU/ST/AF=gTTS fallback if pyttsx3 unavailable\n"
        "   - gTTS fallback: generate mp3 to temp file, play via playsound\n"
        "   - speak_queue: Queue so TTS calls don't block engines\n"
        "   - Announce every overlay notification audibly\n\n"
        "4. SCREEN READING\n"
        "   - read_screen_region(x, y, w, h): OCR via pytesseract → speak result\n"
        "   - read_focused_element(): reads the element under the gaze cursor\n"
        "   - Auto-announce: when gaze dwells on element >1s, read it aloud\n\n"
        "5. THREADING\n"
        "   - Run in daemon thread\n"
        "   - Accept stop_event: threading.Event\n"
        "   - Read from audio_command_queue, emit to overlay_queue\n\n"
        "Write the COMPLETE audio_engine.py. Every line. Runnable immediately.\n"
    ),
    expected_output="Complete, immediately runnable audio_engine.py.",
    agent=agent_audio,
    context=[task_architect],
)


# ═══════════════════════════════════════════════════════════
# AGENT 6 — COGNITIVE ENGINE + LLM COACH
# Builds screen simplification + GPT-4o coaching
# ═══════════════════════════════════════════════════════════
agent_cognitive = Agent(
    role="Cognitive Accessibility and LLM Integration Engineer",
    goal=(
        "Build cognitive_engine.py and llm_coach.py — the screen simplification "
        "system that reduces cognitive load and the Azure GPT-4o powered coaching "
        "system that helps users complete complex tasks step by step."
    ),
    backstory=(
        "You have built cognitive accessibility tools for users with dyslexia, ADHD, "
        "and autism. You know that cognitive overload is not constant — it spikes when "
        "the user makes repeated errors or pauses for >10 seconds on a task. "
        "When overload is detected, the screen simplification overlay activates: "
        "it dims everything except the focused element, increases font size, "
        "reduces visual noise. When the user completes a step, it celebrates briefly. "
        "For the LLM coach: you use AzureChatOpenAI with a system prompt that makes "
        "GPT-4o act as a patient, non-infantilizing assistant. The coach watches "
        "what the user is doing (screen context) and offers the next step only "
        "when asked or when the user seems stuck. It never assumes incompetence. "
        "The coach speaks in the user's language (EN/ZU/ST/AF) using the audio engine."
    ),
    tools=[],
    llm=llm_builder,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_cognitive = Task(
    description=(
        f"{BUILD_CONTEXT}\n\n"
        "YOUR TASK: Write the complete cognitive_engine.py and llm_coach.py files.\n\n"
        "cognitive_engine.py MUST IMPLEMENT:\n\n"
        "1. COGNITIVE LOAD DETECTION\n"
        "   - Monitor: error rate (from motor_queue), pause duration, correction count\n"
        "   - Cognitive load score: 0-100, updated every 5 seconds\n"
        "   - Thresholds: LOW<30, MEDIUM 30-60, HIGH>60\n"
        "   - HIGH load triggers: screen simplification + coaching offer\n\n"
        "2. SCREEN SIMPLIFICATION OVERLAY\n"
        "   - pyautogui screenshot → identify active window region\n"
        "   - tkinter overlay: dim all except focused element (semi-transparent black rect)\n"
        "   - Increase font size of focused element text (accessibility zoom)\n"
        "   - Reading guide: horizontal line following cursor for dyslexia\n"
        "   - Colour blind modes: deuteranopia/protanopia/tritanopia filters\n\n"
        "3. TASK COACHING\n"
        "   - Detect common task contexts: email composition, form filling, web browsing\n"
        "   - Offer next-step hints via overlay notification\n"
        "   - Track task completion: celebrate (green flash) on success\n\n"
        "llm_coach.py MUST IMPLEMENT:\n\n"
        "4. AZURE GPT-4O INTEGRATION\n"
        "   - AzureChatOpenAI from langchain_openai\n"
        "   - System prompt: patient, non-infantilizing coach in user's language\n"
        "   - get_coaching_hint(task_context, user_language): → str hint\n"
        "   - get_form_help(form_field_name, user_language): → str guidance\n"
        "   - summarise_screen(screenshot_text, user_language): → str summary\n"
        "   - All calls async-wrapped so they don't block the UI\n"
        "   - Offline fallback: preloaded hints dict for common tasks (no API call)\n\n"
        "Write COMPLETE cognitive_engine.py and llm_coach.py. Every line. Runnable immediately.\n"
    ),
    expected_output="Complete cognitive_engine.py and llm_coach.py — runnable immediately.",
    agent=agent_cognitive,
    context=[task_architect, task_overlay],
)


# ═══════════════════════════════════════════════════════════
# AGENT 7 — USER PROFILE ENGINEER
# Builds the SQLite learning profile system
# ═══════════════════════════════════════════════════════════
agent_profile = Agent(
    role="User Profile and Adaptive Learning Engineer",
    goal=(
        "Build user_profile.py — the SQLite-backed system that learns each user's "
        "specific disability profile over time and makes every engine smarter with use."
    ),
    backstory=(
        "You build adaptive systems that get better the more they're used. "
        "You know that for this application, the learning loop is the killer feature: "
        "day 1 the tremor filter is generic, day 7 it knows exactly this user's "
        "4.2Hz tremor and filters it with surgical precision. "
        "You use SQLite because it's stdlib, offline, and fast enough for this use case. "
        "You store: tremor frequency profile, baseline EAR for gaze, "
        "personal vocabulary (for typing prediction), error correction history, "
        "preferred language, feature toggle preferences, session stats. "
        "You expose a clean API that every engine can call to read/write its slice "
        "of the profile without knowing about the others."
    ),
    tools=[],
    llm=llm_builder,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_profile = Task(
    description=(
        f"{BUILD_CONTEXT}\n\n"
        "YOUR TASK: Write the complete user_profile.py file.\n\n"
        "MUST IMPLEMENT:\n\n"
        "1. SQLITE SCHEMA\n"
        "   Table: user_settings (language, feature_toggles JSON, created_at)\n"
        "   Table: gaze_profile (baseline_ear, dwell_ms, calibration_data JSON)\n"
        "   Table: motor_profile (tremor_freq, kalman_q, kalman_r, double_key_ms, typing_corrections JSON)\n"
        "   Table: session_stats (date, corrections_made, gaze_clicks, voice_commands, duration_mins)\n"
        "   Table: vocabulary (word, frequency, last_used — for typing prediction)\n\n"
        "2. PROFILE API\n"
        "   - load_profile() → dict: loads all settings, creates defaults if first run\n"
        "   - save_gaze_profile(ear_baseline, dwell_ms)\n"
        "   - save_motor_profile(tremor_freq, kalman_params, double_key_ms)\n"
        "   - update_vocabulary(word): increment frequency or insert\n"
        "   - get_top_words(n=10) → list: most frequent words for prediction\n"
        "   - log_session(stats_dict)\n"
        "   - get_session_summary() → dict: total usage stats\n"
        "   - reset_profile(): wipe all learned data, keep settings\n\n"
        "3. FIRST-RUN CALIBRATION\n"
        "   - is_first_run() → bool\n"
        "   - run_gaze_calibration_sequence() → saves baseline EAR\n"
        "   - run_typing_calibration() → records baseline error rate\n\n"
        "Write the COMPLETE user_profile.py. Every line. Runnable immediately.\n"
    ),
    expected_output="Complete user_profile.py — runnable immediately.",
    agent=agent_profile,
    context=[task_architect],
)


# ═══════════════════════════════════════════════════════════
# AGENT 8 — QA ENGINEER
# Writes integration tests and validates the demo works
# ═══════════════════════════════════════════════════════════
agent_qa = Agent(
    role="QA Engineer and Demo Validation Specialist",
    goal=(
        "Write the integration tests, the requirements.txt with pinned versions, "
        "and validate that all 4 demo features work as described in the brief. "
        "Find every integration bug before the build crew hits it."
    ),
    backstory=(
        "You have been the QA engineer on 20 hackathon teams and you have saved "
        "every single one from demo failure. You know the failure modes: "
        "pynput conflicts with tkinter on Windows when both run in the main thread. "
        "MediaPipe and OpenCV version mismatches cause silent import failures. "
        "whisper-tiny needs ffmpeg on Windows — if it's not installed, the demo dies. "
        "pyautogui fails if the screen DPI scaling is not 100% on Windows. "
        "You write tests that simulate the exact demo sequence and catch failures "
        "before they happen on stage. You also write the requirements.txt with "
        "exact pinned versions that are known to work together."
    ),
    tools=[search_tool],
    llm=llm_builder,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_qa = Task(
    description=(
        f"{BUILD_CONTEXT}\n\n"
        "YOUR TASK: Write requirements.txt, test_integration.py, and README.md.\n\n"
        "requirements.txt MUST:\n"
        "   - Pin every dependency to exact versions known to work together on Python 3.11 Windows\n"
        "   - Include: mediapipe, opencv-python, pynput, pyautogui, openai-whisper,\n"
        "     pyttsx3, gTTS, playsound, sounddevice, pystray, Pillow, scikit-learn,\n"
        "     numpy, langchain-openai, openai, python-dotenv, pytesseract\n"
        "   - Add comments for any package with non-obvious install steps\n"
        "   - Note: ffmpeg required separately for whisper on Windows\n\n"
        "test_integration.py MUST:\n"
        "   - Test 1: import all modules without error\n"
        "   - Test 2: webcam available and MediaPipe initialises\n"
        "   - Test 3: Kalman filter produces smoothed output from noisy input\n"
        "   - Test 4: pynput keyboard hook fires and correction applies\n"
        "   - Test 5: pyttsx3 speaks a test sentence\n"
        "   - Test 6: whisper-tiny loads and transcribes a test audio file\n"
        "   - Test 7: SQLite profile creates, writes, reads correctly\n"
        "   - Test 8: overlay window opens, shows status, closes cleanly\n"
        "   - Test 9: tray icon creates without error\n"
        "   - Test 10: DEMO SEQUENCE — simulate the full demo flow end-to-end\n"
        "   - Each test: clear pass/fail output with fix suggestion on failure\n\n"
        "README.md MUST:\n"
        "   - One-command install: pip install -r requirements.txt\n"
        "   - ffmpeg install instructions for Windows\n"
        "   - .env setup (what variables, where to get values)\n"
        "   - How to run: python main.py\n"
        "   - How to run tests: python test_integration.py\n"
        "   - Demo sequence: exact steps to reproduce the hackathon demo\n"
        "   - Troubleshooting: top 5 failure modes and fixes\n\n"
        "Write COMPLETE requirements.txt, test_integration.py, and README.md.\n"
    ),
    expected_output="Complete requirements.txt, test_integration.py, and README.md.",
    agent=agent_qa,
    context=[task_architect, task_gaze, task_motor, task_overlay, task_audio, task_cognitive, task_profile],
)


# ═══════════════════════════════════════════════════════════
# AGENT 9 — DEMO DIRECTOR
# Writes the final video script and submission checklist
# ═══════════════════════════════════════════════════════════
agent_demo = Agent(
    role="Hackathon Demo Director and Submission Specialist",
    goal=(
        "Write the complete timestamped demo video script, the exact spoken words "
        "for every moment, and the submission checklist that ensures nothing is "
        "missed before the Sunday 17:00 deadline."
    ),
    backstory=(
        "You have directed 40 winning hackathon demos. Your rule: the demo is the product. "
        "You know exactly how to structure the 2-4 minute video: "
        "0:00-0:30 — human story (no tech, pure emotion) "
        "0:30-1:00 — the impossibility (show the problem live) "
        "1:00-1:30 — the activation (the layer turns on — WOW MOMENT) "
        "1:30-2:30 — the features (each one clean, each one undeniable) "
        "2:30-3:00 — the offline moment (load-shedding resilience) "
        "3:00-3:30 — the multilingual moment "
        "3:30-4:00 — the close (future vision + call to action) "
        "For the Unified Intent Amplifier, the WOW MOMENT is: "
        "Lebo's hand shaking as he tries to type his name. Every letter a battle. "
        "Then the layer activates. His name appears — perfectly — in one smooth motion. "
        "The room goes quiet. That silence is the win."
    ),
    tools=[],
    llm=llm_creative,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_demo = Task(
    description=(
        f"{BUILD_CONTEXT}\n\n"
        "YOUR TASK: Write the demo video script and submission checklist.\n\n"
        "DELIVER:\n\n"
        "1. COMPLETE TIMESTAMPED VIDEO SCRIPT (3-4 minutes)\n"
        "   Every timestamp: what is ON SCREEN + EXACT WORDS SPOKEN\n"
        "   Mark: [WOW MOMENT], [MULTILINGUAL MOMENT], [OFFLINE MOMENT]\n"
        "   The opening 30 seconds: Lebo's story — specific, human, no jargon\n"
        "   The WOW MOMENT: tremor typing → layer on → perfect text\n"
        "   Show all 4 live demo features in sequence\n\n"
        "2. PRESENTER NOTES\n"
        "   What to say at each moment\n"
        "   What to click/demonstrate\n"
        "   What not to say (avoid jargon list)\n"
        "   Recovery lines if something fails live\n\n"
        "3. SUBMISSION CHECKLIST\n"
        "   Every item needed by Sunday 17:00:\n"
        "   [ ] Working prototype (all 4 features)\n"
        "   [ ] Demo video (2-10 min)\n"
        "   [ ] project_brief.md\n"
        "   [ ] README with setup instructions\n"
        "   [ ] ... (complete the list)\n\n"
        "4. JUDGE SCORING GUIDE\n"
        "   For each judging criterion — what specific moment in the demo scores it:\n"
        "   Innovation: ...\n"
        "   Real-world impact: ...\n"
        "   Technical execution: ...\n"
        "   AI-native: ...\n"
        "   Demo clarity: ...\n"
    ),
    expected_output=(
        "Complete timestamped video script with exact spoken words. "
        "Presenter notes. Submission checklist. Judge scoring guide."
    ),
    agent=agent_demo,
    context=[task_architect, task_gaze, task_motor, task_overlay, task_audio, task_cognitive, task_qa],
)


# ═══════════════════════════════════════════════════════════
# ASSEMBLE THE BUILD CREW
# Hierarchical: architect designs, specialists build in parallel context
# Sequential used here for reliability on older CrewAI
# ═══════════════════════════════════════════════════════════
build_crew = Crew(
    agents=[
        agent_architect,
        agent_gaze,
        agent_motor,
        agent_overlay,
        agent_audio,
        agent_cognitive,
        agent_profile,
        agent_qa,
        agent_demo,
    ],
    tasks=[
        task_architect,
        task_gaze,
        task_motor,
        task_overlay,
        task_audio,
        task_cognitive,
        task_profile,
        task_qa,
        task_demo,
    ],
    process=Process.sequential,
    verbose=True,
    memory=False,
)


# ═══════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ISAZI HACKATHON — PHASE 2: BUILD CREW")
    print("  Unified Intent Amplifier")
    print(f"  Model   : Azure OpenAI GPT-4o")
    print(f"  Deploy  : {AZURE_DEPLOYMENT}")
    print(f"  Agents  : 9  |  Process : Sequential")
    print("  ETA     : 30 – 60 minutes")
    print("  Output  : unified_intent_amplifier/ directory")
    print("=" * 60 + "\n")

    result = build_crew.kickoff()

    print("\n" + "=" * 60)
    print("  PHASE 2 COMPLETE")
    print("")
    print("  Your build crew has generated the complete codebase.")
    print("  Next steps:")
    print("  1. pip install -r unified_intent_amplifier/requirements.txt")
    print("  2. Copy your .env into unified_intent_amplifier/")
    print("  3. python unified_intent_amplifier/test_integration.py")
    print("  4. python unified_intent_amplifier/main.py")
    print("  5. Record the demo video using the script provided")
    print("=" * 60 + "\n")

    print(result)
