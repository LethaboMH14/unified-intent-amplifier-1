"""
=============================================================
UNIFIED INTENT AMPLIFIER — PhD Multi-Agent Fix Crew
=============================================================
A hierarchical multi-level AI system that diagnoses every bug
in the UIA codebase and rewrites each file with verified fixes.

ARCHITECTURE:
  Chief Scientist (manager)
    ├── Division 1: Diagnostics Team (2 agents)
    │     ├── Bug Archaeologist      — finds root causes
    │     └── Dependency Auditor     — checks imports/versions
    ├── Division 2: Engineering Team (4 agents)
    │     ├── Gaze Engineer          — fixes gaze_engine.py
    │     ├── Motor Engineer         — fixes motor_engine.py
    │     ├── Audio Engineer         — fixes audio_engine.py
    │     └── UI Engineer            — fixes overlay.py + tray_app.py + main.py
    └── Division 3: QA Team (2 agents)
          ├── Test Writer            — writes/updates test_integration.py
          └── Integration Validator  — final verification pass

KNOWN BUGS BEING FIXED:
  1. Gaze shaky  — EMA alpha 0.10 is too reactive; no Kalman; missing dead zone
  2. Tremor weak — Kalman Q=0.01/R=0.1 too loose; no intentional-move passthrough
  3. Audio silent — spatial cue only fires on toggle-on, never continuously
  4. Tray missing — pystray runs in daemon thread on Windows (must be main thread)
  5. config.py    — IRIS indices wrong (474-477 = right eye, not left)

RUN:
  python fix_crew.py
  
  Then copy the fixed files from fixed_files/ into unified_intent_amplifier/
  and run: python unified_intent_amplifier/main.py
=============================================================
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from langchain_openai import AzureChatOpenAI

load_dotenv()

# ── LLM Config ────────────────────────────────────────────
def make_llm(temperature=0.2):
    return AzureChatOpenAI(
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        temperature=temperature,
        max_tokens=4096,
    )

llm_manager   = make_llm(temperature=0.1)   # manager — precise
llm_diagnosis = make_llm(temperature=0.2)   # diagnosis — careful
llm_engineer  = make_llm(temperature=0.15)  # engineering — exact code
llm_qa        = make_llm(temperature=0.1)   # QA — deterministic

# ── Load source files for context ─────────────────────────
SRC = Path(__file__).parent / "unified_intent_amplifier"

def read_src(filename):
    p = SRC / filename
    return p.read_text(encoding="utf-8") if p.exists() else f"[FILE NOT FOUND: {filename}]"

GAZE_SRC    = read_src("gaze_engine.py")
MOTOR_SRC   = read_src("motor_engine.py")
AUDIO_SRC   = read_src("audio_engine.py")
OVERLAY_SRC = read_src("overlay.py")
TRAY_SRC    = read_src("tray_app.py")
MAIN_SRC    = read_src("main.py")
CONFIG_SRC  = read_src("config.py")
TEST_SRC    = read_src("test_integration.py")

# ── Shared context injected into every task ───────────────
SYSTEM_CONTEXT = """
APP: Unified Intent Amplifier (UIA)
PURPOSE: Accessibility app for disabled users — Isazi AI Hackathon
PLATFORM: Windows 11, Python 3.11, VS Code
SCREEN: 1521x776 @ 60cm distance
WEBCAM: 1920x1080
LLM: Azure OpenAI GPT-4o (AzureChatOpenAI via LangChain)

CONFIRMED BUGS FROM USER TESTING:
  BUG-1 GAZE SHAKY: Gaze cursor trembles constantly even when user holds still.
         Root: EMA alpha=0.10 is TOO LOW — causes lag then snap. Need Kalman filter
         + median buffer. Also: no dead zone in screen centre so micro eye wobbles
         move cursor. Also: IRIS_LEFT_IDX=[474,475,476,477] is WRONG in config.py —
         those are right eye iris. Left iris = [469,470,471,472]. This causes
         crossed mapping where looking left moves cursor right.
  
  BUG-2 TREMOR NOT VISIBLE: Kalman Q=0.01 R=0.1 settings are too loose — filter
         barely smooths at 50Hz polling. Also tremor_loop applies smoothing to ALL
         movements including intentional large moves, making cursor feel sticky and
         unresponsive. Need to detect move delta and only smooth small tremor moves.
  
  BUG-3 SPATIAL AUDIO SILENT: audio_engine.play_spatial_cue() IS implemented but
         in tray_app.py _toggle("audio") only calls play_spatial_cue("centre",523)
         once on toggle-on. User toggles, hears one beep, then nothing. Need:
         (a) startup L→C→R→C demo sequence confirming it works,
         (b) continuous ambient tick panned to cursor position every 1.5s,
         (c) click sound on gaze blink events.
  
  BUG-4 TRAY MISSING: TrayApp.start() launches pystray in a daemon thread.
         Windows requires pystray.Icon.run() on the MAIN thread. Since main.py
         runs overlay.run() (tkinter mainloop) on the main thread, tray gets
         a daemon thread which Windows silently kills. Fix: run tkinter HUD in
         a thread, run pystray on main thread.
  
  BUG-5 CONFIG IRIS INDICES WRONG:
         IRIS_LEFT_IDX  = [474, 475, 476, 477]  ← WRONG (these are right eye)
         IRIS_RIGHT_IDX = [469, 470, 471, 472]  ← WRONG (these are left eye)
         MediaPipe refined mesh: Left iris=468-472, Right iris=473-477.
         This means gaze is MIRRORED — looking left moves cursor right.

OUTPUT REQUIREMENT: Write complete, runnable Python files. No placeholders.
No "# ... rest of code unchanged". Every function. Every import. Full file.
"""


# ═══════════════════════════════════════════════════════════════
# DIVISION 1 — DIAGNOSTICS TEAM
# ═══════════════════════════════════════════════════════════════

agent_bug_archaeologist = Agent(
    role="Senior Bug Archaeologist",
    goal=(
        "Perform deep root-cause analysis of all 5 confirmed bugs. "
        "Trace each bug to its exact line number and mechanism. "
        "Produce a precise diagnosis report that engineers can act on."
    ),
    backstory=(
        "You are a PhD-level debugging specialist with 15 years of experience "
        "in real-time signal processing and computer vision systems. You have "
        "debugged MediaPipe gaze trackers, Kalman filter implementations, and "
        "Windows GUI threading issues. You think in terms of signal theory and "
        "OS threading models. You never guess — you trace every bug to its "
        "mathematical or architectural root cause."
    ),
    llm=llm_diagnosis,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_diagnosis = Task(
    description=(
        f"{SYSTEM_CONTEXT}\n\n"
        "CURRENT SOURCE FILES FOR ANALYSIS:\n\n"
        f"=== config.py ===\n{CONFIG_SRC}\n\n"
        f"=== gaze_engine.py ===\n{GAZE_SRC}\n\n"
        f"=== motor_engine.py ===\n{MOTOR_SRC}\n\n"
        f"=== audio_engine.py ===\n{AUDIO_SRC}\n\n"
        f"=== tray_app.py ===\n{TRAY_SRC}\n\n"
        f"=== main.py ===\n{MAIN_SRC}\n\n"
        "YOUR TASK:\n"
        "For each of the 5 confirmed bugs, produce:\n"
        "  BUG-N: [Name]\n"
        "  File: [filename]\n"
        "  Line(s): [exact line numbers]\n"
        "  Root cause: [mathematical/architectural explanation]\n"
        "  Evidence: [quote the exact bad code]\n"
        "  Fix strategy: [precise engineering approach]\n"
        "  Side effects to watch: [what else might break]\n\n"
        "Also identify any ADDITIONAL bugs not in the confirmed list.\n"
        "Output as structured diagnosis report."
    ),
    expected_output=(
        "Structured diagnosis report covering all 5 confirmed bugs plus any "
        "additional bugs found, with exact line numbers, root causes, and fix strategies."
    ),
    agent=agent_bug_archaeologist,
)

agent_dependency_auditor = Agent(
    role="Dependency & Threading Auditor",
    goal=(
        "Audit all import dependencies and threading architecture. "
        "Identify version conflicts, Windows-specific threading issues, "
        "and any imports that will fail silently on the user's machine."
    ),
    backstory=(
        "You are a systems architect specialising in Windows Python threading "
        "models, COM initialisation, and library version compatibility. You have "
        "shipped 30+ production Python desktop apps on Windows. You know that "
        "pystray, tkinter, pyttsx3, and sounddevice all have Windows-specific "
        "threading requirements that will silently fail in daemon threads."
    ),
    llm=llm_diagnosis,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_dependency_audit = Task(
    description=(
        f"{SYSTEM_CONTEXT}\n\n"
        f"=== requirements.txt ===\n{read_src('requirements.txt')}\n\n"
        f"=== main.py ===\n{MAIN_SRC}\n\n"
        f"=== tray_app.py ===\n{TRAY_SRC}\n\n"
        f"=== audio_engine.py ===\n{AUDIO_SRC}\n\n"
        "YOUR TASK:\n"
        "Audit the threading architecture and dependencies:\n\n"
        "1. THREADING AUDIT: Map every thread created. For each:\n"
        "   - What runs on it\n"
        "   - Whether it is daemon or not\n"
        "   - Whether Windows allows it (pystray/tkinter/COM need main thread)\n"
        "   - Fix recommendation\n\n"
        "2. DEPENDENCY AUDIT: For each library in requirements.txt:\n"
        "   - Version compatibility with Python 3.11 / Windows 11\n"
        "   - Any known issues with the listed version\n"
        "   - Whether it needs COM initialisation (pyttsx3, sounddevice)\n\n"
        "3. IMPORT FAILURE RISKS: Any import that could fail silently and "
        "cause a feature to appear broken without an error message.\n\n"
        "Output as structured audit report."
    ),
    expected_output=(
        "Thread map with Windows compatibility analysis, dependency version audit, "
        "and import risk assessment with specific fix recommendations."
    ),
    agent=agent_dependency_auditor,
    context=[task_diagnosis],
)


# ═══════════════════════════════════════════════════════════════
# DIVISION 2 — ENGINEERING TEAM
# ═══════════════════════════════════════════════════════════════

agent_gaze_engineer = Agent(
    role="Computer Vision & Gaze Tracking Engineer",
    goal=(
        "Rewrite gaze_engine.py with Kalman filter smoothing, correct iris "
        "landmark indices, proper dead zone, and a 5-point calibration loader "
        "that actually eliminates cursor shaking."
    ),
    backstory=(
        "You have a PhD in computer vision and 8 years of eye-tracking system "
        "development. You have implemented Kalman filters for gaze stabilisation "
        "in clinical assistive technology devices. You know MediaPipe FaceMesh "
        "landmark indices by heart. You know that EMA with alpha=0.10 causes "
        "lag-then-snap, that iris landmark indices 468-472 are LEFT eye and "
        "473-477 are RIGHT eye, and that a dead zone in screen centre is "
        "essential to prevent micro-saccade noise from moving the cursor."
    ),
    llm=llm_engineer,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_fix_gaze = Task(
    description=(
        f"{SYSTEM_CONTEXT}\n\n"
        f"=== CURRENT gaze_engine.py ===\n{GAZE_SRC}\n\n"
        f"=== CURRENT config.py ===\n{CONFIG_SRC}\n\n"
        "DIAGNOSIS CONTEXT: (from diagnosis team)\n"
        "  - IRIS_LEFT_IDX and IRIS_RIGHT_IDX are SWAPPED in config.py\n"
        "    Correct: Left iris = [469,470,471,472], Right iris = [473,474,475,476]\n"
        "  - EMA alpha=0.10 causes lag-snap behaviour, not smooth tracking\n"
        "  - No dead zone: micro eye wobbles move cursor when user looks centre\n"
        "  - No Kalman filter — only EMA which doesn't model velocity\n"
        "  - Calibration loads from DB but the mapping formula in gaze_engine\n"
        "    uses eye_x_min/max but calibrate_gaze.py saves scale_x/offset_x\n"
        "    These are INCOMPATIBLE — calibration data never actually gets used\n\n"
        "WRITE THE COMPLETE FIXED gaze_engine.py:\n"
        "Requirements:\n"
        "  1. Fix iris indices: use LEFT=[469,470,471,472] RIGHT=[473,474,475,476]\n"
        "  2. Replace EMA with proper 2D OpenCV Kalman filter (4-state: x,y,vx,vy)\n"
        "  3. Add 5-frame median buffer BEFORE Kalman to remove spike noise\n"
        "  4. Dead zone: if normalised gaze within 0.04 of screen centre, hold position\n"
        "  5. Fix calibration: load scale_x, offset_x, scale_y, offset_y from DB\n"
        "     Apply: screen_x = scale_x * eye_ratio_x + offset_x (then * screen_w)\n"
        "  6. Keep all existing class structure, imports, and the singleton at bottom\n"
        "  7. Keep all imports from config.py — update config constants in the fix\n\n"
        "ALSO WRITE the corrected config.py section for iris indices.\n\n"
        "Output format:\n"
        "=== FIXED: gaze_engine.py ===\n[complete file]\n\n"
        "=== FIXED: config.py iris indices section ===\n[just the changed lines]\n"
    ),
    expected_output=(
        "Complete fixed gaze_engine.py with Kalman filter, correct iris indices, "
        "dead zone, and working calibration. Plus the corrected config.py iris lines."
    ),
    agent=agent_gaze_engineer,
    context=[task_diagnosis, task_dependency_audit],
    output_file="fixed_files/gaze_engine.py",
)

agent_motor_engineer = Agent(
    role="Real-Time Motor Signal Processing Engineer",
    goal=(
        "Rewrite motor_engine.py so tremor smoothing is visibly effective — "
        "eliminates shaking without making intentional movements feel sticky."
    ),
    backstory=(
        "You specialise in real-time signal processing for motor disability "
        "assistive technology. You have tuned Kalman filters for hand tremor "
        "compensation in clinical settings. You know that tremor frequency is "
        "4-12Hz, intentional mouse movements are 0-3Hz, and that the key to "
        "separating them is delta-velocity thresholding, not just smoothing gain. "
        "You also know that pynput keyboard listener cannot suppress keystrokes "
        "without admin rights on Windows — it can only observe."
    ),
    llm=llm_engineer,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_fix_motor = Task(
    description=(
        f"{SYSTEM_CONTEXT}\n\n"
        f"=== CURRENT motor_engine.py ===\n{MOTOR_SRC}\n\n"
        f"=== CURRENT config.py ===\n{CONFIG_SRC}\n\n"
        "DIAGNOSIS:\n"
        "  - Kalman Q=0.01 R=0.1: produces almost no smoothing at 50Hz\n"
        "    At 50Hz the filter barely distinguishes signal from noise\n"
        "    Need Q=0.001 R=2.0 for strong tremor suppression\n"
        "  - _tremor_loop smooths ALL movements including fast intentional moves\n"
        "    Result: cursor feels sticky and laggy during normal use\n"
        "    Fix: compute delta from last ANCHORED position, only smooth if\n"
        "    delta < 20px (tremor signature). Large delta = intentional move,\n"
        "    update anchor and pass through unchanged.\n"
        "  - Polling at 50Hz (0.02s) is fine but apply smoothing every frame\n"
        "    not just when abs(sx-x)>2 — the threshold hides small corrections\n"
        "  - TypingCorrector can detect duplicates but CANNOT suppress on Windows\n"
        "    without admin rights. Should change to autocorrect common words instead\n\n"
        "WRITE THE COMPLETE FIXED motor_engine.py:\n"
        "Requirements:\n"
        "  1. Change Kalman params: Q=0.001, R=2.0 (in config.py update too)\n"
        "  2. Add intentional-move detection: track 'anchor' position\n"
        "     If delta from anchor < TREMOR_DELTA_THRESHOLD (20px): apply Kalman\n"
        "     If delta >= threshold: update anchor to current pos, pass through\n"
        "  3. Poll at 60Hz (not 50Hz) — remove the abs()>2 threshold guard\n"
        "  4. TypingCorrector: change from duplicate-suppress to word-autocorrect\n"
        "     Listen for space/enter, check last word against corrections dict\n"
        "     Use pyautogui to backspace + retype correction\n"
        "  5. Keep all existing class structure and the singleton\n\n"
        "Output: === FIXED: motor_engine.py ===\n[complete file]"
    ),
    expected_output=(
        "Complete fixed motor_engine.py with properly tuned Kalman, "
        "intentional-move passthrough, 60Hz polling, and word autocorrect."
    ),
    agent=agent_motor_engineer,
    context=[task_diagnosis, task_dependency_audit],
    output_file="fixed_files/motor_engine.py",
)

agent_audio_engineer = Agent(
    role="Spatial Audio & Accessibility Sound Designer",
    goal=(
        "Fix audio_engine.py so spatial audio is continuously present and "
        "immediately audible when toggled on — not just a single beep."
    ),
    backstory=(
        "You design audio feedback systems for accessibility technology. "
        "You have built spatial audio engines for blind users that provide "
        "continuous positional awareness. You know that sounddevice on Windows "
        "needs blocking=False for non-blocking playback, that pyttsx3 must "
        "init on the same thread it speaks from (COM requirement), and that "
        "accessibility audio feedback must be immediate and unmistakeable."
    ),
    llm=llm_engineer,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_fix_audio = Task(
    description=(
        f"{SYSTEM_CONTEXT}\n\n"
        f"=== CURRENT audio_engine.py ===\n{AUDIO_SRC}\n\n"
        f"=== CURRENT tray_app.py (where audio toggle is) ===\n{TRAY_SRC}\n\n"
        f"=== CURRENT main.py (audio toggle callback) ===\n{MAIN_SRC}\n\n"
        "DIAGNOSIS:\n"
        "  - AudioEngine has play_spatial_cue() which works correctly\n"
        "  - BUT: there is no continuous ambient audio loop\n"
        "    User toggles ON → hears one cue → silence forever\n"
        "  - BUG in main.py _on_audio_toggle: plays L/C/R sequence but\n"
        "    no persistent ambient feedback after that\n"
        "  - pyttsx3 _init_tts runs in _tts_worker thread — CoInitialize\n"
        "    warning happens because pyttsx3 COM needs to be initialised\n"
        "    with pythoncom.CoInitialize() at top of that thread\n"
        "  - sounddevice sd.play() with blocking=False is correct — keep this\n\n"
        "WRITE THE COMPLETE FIXED audio_engine.py:\n"
        "Requirements:\n"
        "  1. Add _ambient_loop method that runs while audio is enabled\n"
        "     Every 1.5 seconds: get cursor X position, compute pan (-1 to +1)\n"
        "     Play a soft 480Hz tone (volume 0.15) panned to cursor position\n"
        "     This gives continuous spatial position feedback\n"
        "  2. Add play_startup_sequence() method:\n"
        "     Plays L(520Hz) → C(440Hz) → R(380Hz) → C(440Hz) with 0.2s gaps\n"
        "     Called when spatial audio is toggled ON\n"
        "  3. Add play_click_sound(cursor_x) method for gaze blink clicks\n"
        "     Short 660Hz tone panned to cursor position\n"
        "  4. Add toggle() method that AudioEngine exposes:\n"
        "     Sets self.enabled, starts/stops ambient loop, plays startup seq\n"
        "  5. Fix pyttsx3 CoInitialize: add 'import pythoncom; pythoncom.CoInitialize()'\n"
        "     at start of _tts_worker (wrap in try/except ImportError)\n"
        "  6. Keep all existing methods: speak, play_spatial_cue, transcribe, etc.\n"
        "  7. Keep the singleton at bottom\n\n"
        "Output: === FIXED: audio_engine.py ===\n[complete file]"
    ),
    expected_output=(
        "Complete fixed audio_engine.py with ambient cursor-following spatial audio loop, "
        "startup confirmation sequence, click sounds, and pyttsx3 COM fix."
    ),
    agent=agent_audio_engineer,
    context=[task_diagnosis, task_dependency_audit],
    output_file="fixed_files/audio_engine.py",
)

agent_ui_engineer = Agent(
    role="Windows Desktop UI & Threading Architect",
    goal=(
        "Fix the tray icon (pystray must run on main thread), update main.py "
        "threading model, update overlay.py to wire the fixed audio toggle, "
        "and update tray_app.py to use the new audio engine methods."
    ),
    backstory=(
        "You are a senior Windows desktop application architect who has shipped "
        "15 system tray applications in Python. You know Windows GUI threading "
        "rules cold: pystray needs the main thread, tkinter needs its own thread "
        "or the main thread, pyttsx3 needs COM initialisation. You have solved "
        "the exact problem of running both a tkinter HUD and a pystray tray icon "
        "simultaneously by running tkinter in a thread and pystray on main."
    ),
    llm=llm_engineer,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_fix_ui = Task(
    description=(
        f"{SYSTEM_CONTEXT}\n\n"
        f"=== CURRENT main.py ===\n{MAIN_SRC}\n\n"
        f"=== CURRENT overlay.py ===\n{OVERLAY_SRC}\n\n"
        f"=== CURRENT tray_app.py ===\n{TRAY_SRC}\n\n"
        "DIAGNOSIS:\n"
        "  - main.py: overlay.run() runs tkinter on MAIN thread\n"
        "    TrayApp.start() spawns a daemon thread for pystray\n"
        "    Windows kills the tray icon silently because pystray.Icon.run()\n"
        "    MUST execute on the main thread\n"
        "  - Fix: swap them — run tkinter HUD in a daemon thread, run pystray\n"
        "    Icon.run() on the main thread (it blocks, which is fine for main)\n"
        "  - tray_app.py _toggle('audio'): only calls play_spatial_cue once\n"
        "    Should call audio_engine.toggle() instead (the new method)\n"
        "  - overlay.py on_toggle['audio'] in main.py calls _on_audio_toggle\n"
        "    Should also call audio_engine.toggle()\n"
        "  - overlay.py is fine as-is for the UI — keep all its code\n\n"
        "WRITE THESE THREE COMPLETE FIXED FILES:\n\n"
        "=== FIXED: main.py ===\n"
        "  - Run overlay.run_in_thread() (already has this method)\n"
        "  - Then run TrayApp on the MAIN thread: tray._icon.run() directly\n"
        "    (not tray.start() which spawns a thread)\n"
        "  - Wire audio toggle to audio_engine.toggle()\n"
        "  - Keep all other engine wiring identical\n\n"
        "=== FIXED: tray_app.py ===\n"
        "  - Change audio toggle: call audio_engine.toggle() not play_spatial_cue\n"
        "  - Keep all other toggle handlers identical\n"
        "  - Remove the start() thread method — main.py will call icon.run() directly\n"
        "  - Add get_icon() method that returns the built pystray.Icon object\n\n"
        "=== FIXED: overlay.py ===\n"
        "  - No structural changes needed\n"
        "  - Just ensure run_in_thread() is present and correct\n"
        "  - Keep all existing toggle and drag code\n\n"
        "Output: complete versions of all three files."
    ),
    expected_output=(
        "Complete fixed main.py, tray_app.py, and overlay.py. "
        "Tray on main thread, HUD in a thread, audio toggle wired to toggle()."
    ),
    agent=agent_ui_engineer,
    context=[task_diagnosis, task_dependency_audit, task_fix_audio],
    output_file="fixed_files/main.py",
)


# ═══════════════════════════════════════════════════════════════
# DIVISION 3 — QA TEAM
# ═══════════════════════════════════════════════════════════════

agent_test_writer = Agent(
    role="Senior QA Engineer & Test Architect",
    goal=(
        "Rewrite test_integration.py to verify all 5 fixes work correctly. "
        "Add specific regression tests for each bug that was fixed."
    ),
    backstory=(
        "You are a test architect who writes the tests that actually catch bugs "
        "rather than just passing green. You write tests that would have caught "
        "each of the 5 bugs before they shipped. You know pytest and unittest "
        "and you know how to test threading code, signal processing code, and "
        "Windows GUI code without requiring a real display or real hardware."
    ),
    llm=llm_qa,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_write_tests = Task(
    description=(
        f"{SYSTEM_CONTEXT}\n\n"
        f"=== CURRENT test_integration.py ===\n{TEST_SRC}\n\n"
        "YOUR TASK: Rewrite test_integration.py with tests that verify all fixes.\n\n"
        "KEEP all existing passing tests. ADD these new regression tests:\n\n"
        "TestGazeEngineFixed:\n"
        "  - test_iris_indices_correct: verify IRIS_LEFT_IDX=[469-472] RIGHT=[473-476]\n"
        "  - test_kalman_filter_smoother_than_ema: compare Kalman vs EMA on noisy signal\n"
        "  - test_dead_zone_holds_position: gaze in centre dead zone should not move\n\n"
        "TestMotorEngineFixed:\n"
        "  - test_kalman_params_strong: verify Q<=0.005 and R>=1.0\n"
        "  - test_tremor_only_smooths_small_delta: large moves pass through unsmoothed\n"
        "  - test_small_delta_gets_smoothed: moves < 20px get Kalman applied\n\n"
        "TestAudioEngineFixed:\n"
        "  - test_toggle_starts_ambient_loop: toggle() sets enabled=True\n"
        "  - test_ambient_loop_running_flag: after toggle ON, engine.enabled is True\n"
        "  - test_click_sound_no_crash: play_click_sound(760) should not raise\n"
        "  - test_startup_sequence_no_crash: play_startup_sequence() should not raise\n\n"
        "TestTrayFixed:\n"
        "  - test_tray_has_get_icon_method: TrayApp must have get_icon() method\n"
        "  - test_main_thread_pattern_documented: verify tray.start() is NOT called\n"
        "    in main.py (grep for 'tray.start' in main.py source)\n\n"
        "Output: === FIXED: test_integration.py ===\n[complete file]"
    ),
    expected_output=(
        "Complete updated test_integration.py with all original tests plus "
        "new regression tests for all 5 fixed bugs."
    ),
    agent=agent_test_writer,
    context=[task_fix_gaze, task_fix_motor, task_fix_audio, task_fix_ui],
    output_file="fixed_files/test_integration.py",
)

agent_integration_validator = Agent(
    role="Integration Validation Scientist",
    goal=(
        "Review all fixed files together as a complete system. "
        "Verify interfaces match, no import mismatches, threading model is "
        "consistent, and the app will actually run end-to-end."
    ),
    backstory=(
        "You are a systems integration specialist who reviews entire codebases "
        "for interface mismatches, import cycles, and threading model violations. "
        "You have a gift for finding the one import that changed signature and "
        "will crash at 11pm on Sunday during the demo. You read code like prose "
        "and you can hold the entire call graph in your head."
    ),
    llm=llm_qa,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_validate = Task(
    description=(
        f"{SYSTEM_CONTEXT}\n\n"
        "You will receive the complete fixed versions of all files from the "
        "engineering team. Your job is final integration validation.\n\n"
        "CHECK ALL OF THESE:\n\n"
        "1. IMPORT CONSISTENCY:\n"
        "   - Every 'from X import Y' in each fixed file — does X actually export Y?\n"
        "   - config.py constants referenced in engines — all present?\n"
        "   - No circular imports?\n\n"
        "2. INTERFACE CONTRACTS:\n"
        "   - audio_engine.toggle() exists and returns bool\n"
        "   - audio_engine.play_click_sound(cursor_x) exists\n"
        "   - tray_app.get_icon() exists and returns pystray.Icon\n"
        "   - motor_engine.set_tremor(bool) still exists (called by overlay + tray)\n"
        "   - gaze_engine.set_enabled(bool) still exists\n\n"
        "3. THREADING MODEL:\n"
        "   - main.py: tkinter runs in a thread, pystray on main thread\n"
        "   - No daemon thread running pystray\n"
        "   - audio ambient loop is a daemon thread (fine)\n"
        "   - gaze loop is a daemon thread (fine)\n\n"
        "4. STARTUP SEQUENCE:\n"
        "   - Trace main() from first line to UI running\n"
        "   - Every engine.start() is called before any toggle\n"
        "   - No race conditions in startup\n\n"
        "5. DEMO READINESS:\n"
        "   - When user clicks 'Gaze Control' button: gaze works, no shake\n"
        "   - When user clicks 'Tremor Smooth': only small moves smoothed\n"
        "   - When user clicks 'Spatial Audio': L→C→R sequence plays immediately\n"
        "   - Tray icon visible in Windows system tray\n\n"
        "Output: VALIDATION REPORT with PASS/FAIL for each check. "
        "For any FAIL: provide the exact fix (1-3 lines of code)."
    ),
    expected_output=(
        "Complete validation report with PASS/FAIL for all checks. "
        "Any failures include exact code fixes."
    ),
    agent=agent_integration_validator,
    context=[task_fix_gaze, task_fix_motor, task_fix_audio, task_fix_ui, task_write_tests],
    output_file="fixed_files/VALIDATION_REPORT.md",
)


# ═══════════════════════════════════════════════════════════════
# ASSEMBLE THE FULL PhD CREW
# Hierarchical process with manager agent
# ═══════════════════════════════════════════════════════════════

Path("fixed_files").mkdir(exist_ok=True)

fix_crew = Crew(
    agents=[
        agent_bug_archaeologist,
        agent_dependency_auditor,
        agent_gaze_engineer,
        agent_motor_engineer,
        agent_audio_engineer,
        agent_ui_engineer,
        agent_test_writer,
        agent_integration_validator,
    ],
    tasks=[
        task_diagnosis,
        task_dependency_audit,
        task_fix_gaze,
        task_fix_motor,
        task_fix_audio,
        task_fix_ui,
        task_write_tests,
        task_validate,
    ],
    process=Process.sequential,   # diagnosis → engineering → QA in order
    manager_llm=llm_manager,
    verbose=True,
    memory=False,
)


# ═══════════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  UIA FIX CREW — PhD Multi-Agent System")
    print("  8 agents | 3 divisions | Sequential")
    print("  Fixing: Gaze shake, Tremor, Audio, Tray, Config")
    print("  ETA: 10–20 minutes")
    print("=" * 60 + "\n")

    result = fix_crew.kickoff()

    print("\n" + "=" * 60)
    print("  FIX CREW COMPLETE")
    print("  Fixed files are in: fixed_files/")
    print("")
    print("  NEXT STEPS:")
    print("  1. Copy fixed_files/*.py into unified_intent_amplifier/")
    print("  2. Run: python unified_intent_amplifier/test_integration.py")
    print("  3. All tests pass? Run: python unified_intent_amplifier/calibrate_gaze.py")
    print("  4. Then run: python unified_intent_amplifier/main.py")
    print("=" * 60 + "\n")

    print(result)
