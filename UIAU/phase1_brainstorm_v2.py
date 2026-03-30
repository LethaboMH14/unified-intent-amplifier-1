"""
=============================================================
ISAZI AI ACCESSIBILITY HACKATHON
Phase 1 — Brainstorm Crew V2 — UNIVERSAL ADAPTIVE LAYER
Azure OpenAI GPT-4o + Serper Edition
=============================================================
7 agents. Sequential process.
Output: project_brief.md (hand-off to Phase 2 build crew)

Vision: Not an app. An AI-native adaptive layer that sits on
top of the laptop and reshapes every interaction in real time
for users with cerebral palsy, locked-in syndrome, Parkinson's,
tremors, blindness, deafness, cognitive disabilities — all at
once, using every sensor the laptop has.

SETUP:
  pip install "crewai==0.80.0" "crewai-tools==0.14.0" python-dotenv

.env file needs:
  AZURE_OPENAI_API_KEY=
  AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
  AZURE_OPENAI_DEPLOYMENT=gpt-4o
  AZURE_OPENAI_API_VERSION=2024-08-01-preview
  SERPER_API_KEY=

RUN:
  python phase1_brainstorm_v2.py
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
        raise ValueError(f"\n  Missing environment variable: {var}\n  Add it to your .env file and try again.\n")

llm_creative = LLM(
    model=f"azure/{AZURE_DEPLOYMENT}",
    api_key=AZURE_API_KEY,
    base_url=AZURE_ENDPOINT,
    api_version=AZURE_API_VERSION,
    temperature=0.9,
    max_tokens=4096,
)

llm_precise = LLM(
    model=f"azure/{AZURE_DEPLOYMENT}",
    api_key=AZURE_API_KEY,
    base_url=AZURE_ENDPOINT,
    api_version=AZURE_API_VERSION,
    temperature=0.2,
    max_tokens=8096,
)

search_tool = SerperDevTool(
    api_key=os.getenv("SERPER_API_KEY"),
    n_results=5,
)

# ─────────────────────────────────────────────────────────
# HACKATHON CONTEXT
# ─────────────────────────────────────────────────────────
HACKATHON_CONTEXT = """
HACKATHON : Isazi AI Accessibility Hackathon
ORGANISER : Isazi Consulting (Pty) Ltd — isazi.ai
PARTNER   : UNISA
PRIZE POOL: R52,500 total cash prizes
BUILD TIME: 72 hours (Friday 18:00 → Sunday 17:00)
SUBMISSION: 2–10 minute demo video of a working prototype
JUDGING   : Innovation · Real-world impact · Technical execution · AI-native · Demo clarity

FOCUS AREAS (covering ALL areas = maximum judging score):
  1. Visual disability     — blindness, low vision, colour blindness
  2. Mobility disability   — cerebral palsy, locked-in syndrome, Parkinson's, tremors,
                             limited motor control, wheelchair users
  3. Hearing & speech      — deafness, hard of hearing, speech impairments, non-verbal
  4. Cognitive disability  — dyslexia, ADHD, autism spectrum, memory impairments
  5. Employment barriers   — disabled people struggling to find or keep jobs

PLATFORM: Laptop-first (Windows/Mac). Every hardware sensor available:
  - Webcam (eye tracking, face detection, blink detection, gaze direction)
  - Microphone (voice, breath, ambient sound)
  - Keyboard (pattern analysis, tremor detection, double-typing correction)
  - Mouse/trackpad (tremor compensation, motion smoothing, intent prediction)
  - Screen (full rendering control, overlay layer, contrast adaptation)
  - Speakers/headphones (audio output, spatial audio)
  - Accelerometer if present (motion detection)
  - Battery/power state (offline resilience awareness)

THE CORE VISION — THIS IS NOT AN APP:
  This is an AI-native ADAPTIVE LAYER that sits on top of the OS.
  It observes EVERY input signal from every sensor simultaneously.
  It learns the user's specific disability profile in real time.
  It corrects, predicts, compensates, and amplifies — invisibly.
  A Parkinson's user types and the tremor disappears before the letter lands.
  A locked-in user stares at a word and it executes.
  A blind user moves through the screen by sound alone.
  A cognitively impaired user sees a simplified, calm version of the same screen.
  ALL of this happening at once, for ONE person who may have multiple conditions.
  The AI learns their specific tremor pattern, their specific blink rhythm,
  their specific cognitive load signals — and adapts in real time, getting
  better every hour of use.

SOUTH AFRICA SPECIFIC CONSTRAINTS:
  - Load-shedding up to 8 hours daily — offline resilience is non-negotiable
  - 11 official languages — isiZulu, isiXhosa, Afrikaans, Sesotho most spoken
  - 1 in 3 disabled adults in SA is unemployed (Stats SA)
  - Very low assistive tech ownership — this must run on a standard laptop
  - Must help with employment: job seeking, workplace productivity, SASSA grants
"""

# ═══════════════════════════════════════════════════════════
# AGENT 1 — THE NEUROTECHNOLOGY VISIONARY
# Generates 5 ideas at the intersection of neuroscience,
# AI, and every laptop sensor working together
# ═══════════════════════════════════════════════════════════
agent_visionary = Agent(
    role="Neurotechnology and AI Accessibility Visionary",
    goal=(
        "Generate 5 breakthrough universal adaptive layer concepts that use "
        "every available laptop sensor simultaneously to serve users with "
        "cerebral palsy, locked-in syndrome, Parkinson's, blindness, deafness, "
        "and cognitive disabilities — all at once, in one unified system."
    ),
    backstory=(
        "You are the world's foremost thinker at the intersection of neurotechnology, "
        "AI, and disability. You worked at BrainGate. You consulted for Stephen Hawking's "
        "communication team. You have sat with people who have locked-in syndrome and "
        "watched them fight to communicate one blink at a time for hours. That experience "
        "radicalized you. You now believe the entire assistive tech industry is thinking "
        "too small — building apps when they should be building a new layer of reality. "
        "Your north star: a person with cerebral palsy, Parkinson's, and low vision should "
        "be able to use a standard laptop as fluidly as someone with no disability. "
        "Not with special hardware. Not with expensive devices. With AI watching every "
        "signal and correcting, predicting, amplifying in real time. "
        "You know the exact Python libraries: MediaPipe for face/eye tracking, "
        "PyAutoGUI for mouse control, pynput for keyboard interception, "
        "OpenCV for webcam processing, whisper for voice, pyttsx3 for TTS. "
        "You think in systems, not features. You reject anything that requires "
        "the user to adapt to the technology. The technology adapts to the user."
    ),
    tools=[search_tool],
    llm=llm_creative,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_visionary = Task(
    description=(
        f"{HACKATHON_CONTEXT}\n\n"
        "YOUR TASK:\n"
        "Generate exactly 5 universal adaptive layer concepts.\n\n"
        "EVERY concept MUST:\n"
        "  - Use AT LEAST 3 laptop sensors simultaneously (webcam + keyboard + mouse minimum)\n"
        "  - Serve AT LEAST 4 of the 5 disability focus areas in ONE unified system\n"
        "  - Include a real-time AI learning loop (gets better with every minute of use)\n"
        "  - Be buildable as a working Python prototype in 72 hours\n"
        "  - Have ONE demo moment that makes a room of judges go completely silent\n"
        "  - Work offline during South African load-shedding\n"
        "  - Be something that has never been demoed at a hackathon before\n\n"
        "SPECIFIC CAPABILITIES TO CONSIDER COMBINING:\n"
        "  - Eye gaze tracking via webcam (MediaPipe) → mouse replacement for locked-in users\n"
        "  - Blink detection → click replacement, Morse code input\n"
        "  - Facial expression → emotional state → UI adaptation\n"
        "  - Keyboard pattern analysis → tremor/double-type detection and correction\n"
        "  - Mouse trajectory smoothing → Parkinson's tremor compensation\n"
        "  - Predictive text that learns the user's vocabulary and condition\n"
        "  - Real-time screen reading with spatial audio\n"
        "  - Cognitive load detection via typing pace and error rate\n"
        "  - Voice + breath detection for non-verbal users\n"
        "  - Screen overlay that simplifies complexity for cognitive disabilities\n\n"
        "HARD REJECT any concept that is:\n"
        "  - A single-disability tool (must serve multiple simultaneously)\n"
        "  - Requires special hardware beyond a standard laptop\n"
        "  - A feature that already exists in Windows Accessibility or macOS Accessibility\n"
        "  - A chatbot with accessibility features bolted on\n"
        "  - Anything that requires the user to learn a new interface\n\n"
        "FORMAT each concept EXACTLY like this:\n\n"
        "CONCEPT [N]: [Name]\n"
        "One-line description: ...\n"
        "Disability profiles served simultaneously: ...\n"
        "Sensors used: ...\n"
        "The AI learning loop: (what it learns, how fast, what improves)\n"
        "The 10-second demo moment: ...\n"
        "Why no other team will build this: ...\n"
        "Core Python stack: (exact libraries)\n"
    ),
    expected_output=(
        "Exactly 5 universal adaptive layer concepts. Each with: name, one-line description, "
        "disability profiles served, sensors used, AI learning loop, 10-second demo moment, "
        "uniqueness argument, and exact Python stack."
    ),
    agent=agent_visionary,
)


# ═══════════════════════════════════════════════════════════
# AGENT 2 — THE CLINICAL DISABILITY SPECIALIST
# Validates ideas against real clinical needs and
# lived experience of the specific conditions
# ═══════════════════════════════════════════════════════════
agent_clinical = Agent(
    role="Clinical Disability and Assistive Technology Specialist",
    goal=(
        "Validate each concept against the real clinical needs of people with "
        "cerebral palsy, locked-in syndrome, Parkinson's disease, and combined "
        "sensory/cognitive disabilities — ensuring the technology matches how "
        "these conditions actually manifest, not how they are stereotyped."
    ),
    backstory=(
        "You are a rehabilitation engineer and occupational therapist who has worked "
        "with people with severe physical disabilities for 20 years. You have fitted "
        "AAC devices for non-verbal users. You have watched Parkinson's patients fight "
        "their own hands to type a single sentence. You have sat with locked-in syndrome "
        "patients and learned to read their eye movements. "
        "You know things most engineers don't: Parkinson's tremors are rhythmic at 4-6Hz "
        "and can be filtered with a simple high-pass filter. Cerebral palsy causes "
        "involuntary muscle spasms that are not rhythmic and require intent detection, "
        "not filtering. Locked-in users have PERFECT cognitive function — they are trapped "
        "in a body, not cognitively impaired — so never infantilize the UI for them. "
        "Eye gaze fatigue sets in after 20 minutes — the system must detect this and "
        "switch input modalities automatically. "
        "You score ideas on clinical accuracy and real-world usability, and you flag "
        "any concept that would actually frustrate the people it claims to help."
    ),
    tools=[search_tool],
    llm=llm_creative,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_clinical = Task(
    description=(
        f"{HACKATHON_CONTEXT}\n\n"
        "YOUR TASK:\n"
        "Score each of the 5 concepts from Agent 1 against clinical reality.\n\n"
        "For each concept, assess:\n"
        "  1. CLINICAL ACCURACY: Does the technology match how these conditions actually work?\n"
        "     - Parkinson's tremor: 4-6Hz rhythmic → filterable with signal processing\n"
        "     - Cerebral palsy: non-rhythmic spasms → requires intent prediction, not filtering\n"
        "     - Locked-in syndrome: full cognition, zero or minimal motor output → gaze/blink only\n"
        "     - Cognitive disability: variable load, not constant impairment → adaptive UI\n"
        "  2. FATIGUE MANAGEMENT: Does it account for eye gaze fatigue, voice fatigue, cognitive load?\n"
        "  3. DIGNITY PRESERVATION: Does it treat users as capable adults?\n"
        "  4. SOUTH AFRICA FIT: Works on low-end hardware, survives load-shedding, culturally appropriate?\n"
        "  5. DEMO INTEGRITY: Can the 10-second moment be reproduced live without failure?\n\n"
        "Score each concept 1-10 on each dimension.\n"
        "HARD REJECT any concept scoring below 6 on Clinical Accuracy or Dignity Preservation.\n"
        "Output the TOP 3 concepts with clinical improvement notes for each.\n"
        "For each of the top 3, add: CLINICAL ENHANCEMENT — specific technical improvements\n"
        "that would make the concept clinically accurate and more impressive.\n"
    ),
    expected_output=(
        "Scored assessment of all 5 concepts. Top 3 identified with scores. "
        "Clinical enhancement notes for each of the top 3."
    ),
    agent=agent_clinical,
    context=[task_visionary],
)


# ═══════════════════════════════════════════════════════════
# AGENT 3 — THE LAPTOP SENSOR ARCHITECT
# Maps exactly what can be built with Python on a standard
# laptop in 72 hours, using every available sensor
# ═══════════════════════════════════════════════════════════
agent_sensor_architect = Agent(
    role="Laptop Sensor Integration and Real-Time AI Architect",
    goal=(
        "Map the exact technical implementation for each concept — every sensor, "
        "every library, every AI model, every real-time processing pipeline — "
        "and confirm what is genuinely buildable in 72 hours by a skilled Python team."
    ),
    backstory=(
        "You are a principal engineer who has shipped real-time human-computer interaction "
        "systems. You have built eye trackers from webcams. You have built tremor compensation "
        "systems using only a standard mouse. You know exactly what a laptop can do:\n"
        "WEBCAM: 30fps face mesh (MediaPipe), iris tracking at 4mm accuracy, blink at <100ms\n"
        "KEYBOARD: pynput intercepts every keystroke before OS sees it — you can rewrite reality\n"
        "MOUSE: pynput/pyautogui capture raw coordinates — tremor filter is a 3-line Kalman filter\n"
        "MICROPHONE: whisper.cpp runs offline at 0.3x realtime on CPU — fast enough for live STT\n"
        "SCREEN: pyautogui + win32api give full screen control — overlay with tkinter or pygame\n"
        "GPU: MediaPipe runs on CPU — no GPU needed. whisper-tiny runs on 4GB RAM.\n"
        "You know what fails: OpenCV face tracking drifts in low light. "
        "MediaPipe iris tracking requires the user to be within 60cm of the camera. "
        "pynput keyboard hooks can conflict with admin software on Windows. "
        "You build the technical feasibility map and flag every risk with its mitigation."
    ),
    tools=[search_tool],
    llm=llm_creative,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_sensor_architect = Task(
    description=(
        f"{HACKATHON_CONTEXT}\n\n"
        "YOUR TASK:\n"
        "For each of the top 3 concepts from Agent 2, build the complete technical blueprint.\n\n"
        "For each concept produce:\n\n"
        "SENSOR PIPELINE:\n"
        "  - Webcam feed → which MediaPipe model → what output → how used\n"
        "  - Keyboard stream → pynput hook → what analysis → what correction\n"
        "  - Mouse stream → raw coordinates → which filter → smoothed output\n"
        "  - Microphone → whisper model size → latency → how used\n"
        "  - Screen → overlay approach → rendering library\n\n"
        "AI MODELS REQUIRED:\n"
        "  - List every model with exact HuggingFace name or library\n"
        "  - RAM requirement for each\n"
        "  - CPU-only feasibility (yes/no + why)\n"
        "  - Offline availability (yes/no)\n\n"
        "REAL-TIME LEARNING LOOP:\n"
        "  - What user-specific data is collected (tremor frequency, blink rate, vocab)\n"
        "  - How it is stored (JSON profile, numpy array, SQLite)\n"
        "  - How fast adaptation happens (after 5 mins? 20 mins? 1 hour?)\n"
        "  - What specifically improves (tremor filter sharpness, prediction accuracy)\n\n"
        "72-HOUR BUILD RISK ASSESSMENT:\n"
        "  - GREEN: Can be built in <4 hours\n"
        "  - AMBER: 4-12 hours, doable but needs focus\n"
        "  - RED: >12 hours or likely to fail — suggest cut or simplification\n\n"
        "OFFLINE STRATEGY:\n"
        "  - Which features survive load-shedding with zero internet\n"
        "  - Which models run on CPU only\n"
        "  - What degrades and what the fallback is\n\n"
        "Rank the 3 concepts by: (technical feasibility × impact) and name the winner.\n"
    ),
    expected_output=(
        "Complete technical blueprint for top 3 concepts. Sensor pipelines, AI models, "
        "learning loops, risk assessments, offline strategy. Ranked with winner named."
    ),
    agent=agent_sensor_architect,
    context=[task_visionary, task_clinical],
)


# ═══════════════════════════════════════════════════════════
# AGENT 4 — THE SA EMPLOYMENT BRIDGE
# Ensures the winning concept connects to SA employment
# reality and all 5 judging focus areas
# ═══════════════════════════════════════════════════════════
agent_sa_employment = Agent(
    role="South African Disability Employment and Social Impact Specialist",
    goal=(
        "Ensure the top concept connects powerfully to South African employment reality, "
        "covers all 5 judging focus areas explicitly, and tells a story that makes "
        "SA judges feel the human impact in their chest."
    ),
    backstory=(
        "You grew up in Soweto. Your brother has cerebral palsy and has been rejected "
        "from 47 jobs because employers see his body before his mind. You have worked "
        "at the Department of Labour. You know SASSA disability grant applications "
        "require navigating a website that is almost impossible without full motor control. "
        "You know UIF claims require documents that blind users cannot easily produce. "
        "You know that 1 in 3 disabled adults in SA is unemployed not because they lack "
        "skills but because every digital interface assumes an able body. "
        "You see clearly how a universal adaptive layer changes this: suddenly the SASSA "
        "website works for someone with locked-in syndrome. Suddenly a job interview via "
        "Teams is navigable for someone with Parkinson's. Suddenly a blind person can "
        "compose a professional email using only their voice and AI. "
        "You make sure the concept covers all 5 judging focus areas and that the "
        "employment story is specific, named, and devastating in the best possible way."
    ),
    tools=[search_tool],
    llm=llm_creative,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_sa_employment = Task(
    description=(
        f"{HACKATHON_CONTEXT}\n\n"
        "YOUR TASK:\n"
        "Take the technically winning concept from Agent 3 and ensure it:\n\n"
        "1. COVERS ALL 5 FOCUS AREAS — map exactly how:\n"
        "   - Visual: what specific feature serves blind/low vision users\n"
        "   - Mobility: what specific feature serves cerebral palsy/Parkinson's/locked-in\n"
        "   - Hearing/Speech: what specific feature serves deaf/non-verbal users\n"
        "   - Cognitive: what specific feature serves dyslexia/ADHD/autism users\n"
        "   - Employment: how does this directly help someone get or keep a job in SA\n\n"
        "2. SA EMPLOYMENT INTEGRATION — name exactly:\n"
        "   - Which government digital systems become accessible (SASSA, UIF, job portals)\n"
        "   - What workplace software becomes usable (Teams, Zoom, email, Word)\n"
        "   - What the employment story is (named person, specific barrier, specific solution)\n\n"
        "3. LOAD-SHEDDING EMPLOYMENT SCENARIO:\n"
        "   - What happens when power goes out during a job interview\n"
        "   - What the offline fallback preserves\n\n"
        "4. MULTILINGUAL ACCESSIBILITY:\n"
        "   - How does a isiZulu speaker with cerebral palsy use this system\n"
        "   - Which gTTS codes: en, zu, st, af\n\n"
        "5. JUDGE IMPACT STORY:\n"
        "   Write the human story that opens the demo video.\n"
        "   Named person. Specific SA city. Specific disability. Specific daily barrier.\n"
        "   Specific moment where the adaptive layer changes their life.\n"
        "   30 seconds spoken. No jargon. No statistics. Pure human.\n"
    ),
    expected_output=(
        "All 5 focus areas explicitly mapped. SA employment integration specified. "
        "Load-shedding scenario covered. Multilingual plan confirmed. "
        "Human story written in exact spoken words."
    ),
    agent=agent_sa_employment,
    context=[task_visionary, task_clinical, task_sensor_architect],
)


# ═══════════════════════════════════════════════════════════
# AGENT 5 — THE DEMO DIRECTOR
# Designs the exact 10-second wow moment and the full
# demo video that wins the room
# ═══════════════════════════════════════════════════════════
agent_demo_director = Agent(
    role="Hackathon Demo Director and Presentation Strategist",
    goal=(
        "Design the exact demo sequence that wins the Isazi hackathon — "
        "the specific 10-second moment that makes every judge lean forward, "
        "and the complete timestamped video script that builds to it perfectly."
    ),
    backstory=(
        "You have coached 40 hackathon teams to first place. You have a rule: "
        "'The demo is the product.' You don't care how good the code is if the "
        "demo doesn't land. You know exactly how judges' attention works: "
        "they decide in the first 30 seconds whether they're interested. "
        "If you don't have them by minute 1, you've lost. "
        "Your greatest demos all share one structure: human story → impossibility moment → "
        "the technology makes the impossible happen live → the room goes quiet. "
        "For this project, you are thinking about the specific 10-second moment: "
        "a person with severe Parkinson's tremor tries to type their name — "
        "every letter a battle — and then the layer activates and suddenly, "
        "smoothly, perfectly, their name appears. Or: a locked-in user stares "
        "at an email and it sends. The room doesn't clap. They go quiet first. "
        "That silence is the win. You design for that silence."
    ),
    tools=[],
    llm=llm_creative,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_demo_director = Task(
    description=(
        f"{HACKATHON_CONTEXT}\n\n"
        "YOUR TASK:\n"
        "Design the complete demo strategy for the winning concept.\n\n"
        "DELIVER:\n\n"
        "THE 10-SECOND WOW MOMENT:\n"
        "  Describe frame by frame what is on screen.\n"
        "  What does the presenter do? What does the system do?\n"
        "  What does the audience see that they have never seen before?\n"
        "  Why does the room go quiet?\n\n"
        "THE OPENING 30 SECONDS (human story — exact words to be spoken):\n"
        "  Named person. SA city. Specific disability. Daily battle. \n"
        "  No jargon. No AI buzzwords. Pure human pain.\n\n"
        "FULL TIMESTAMPED VIDEO SCRIPT (2-4 minutes, submission video):\n"
        "  [0:00] — what is on screen + exact words spoken\n"
        "  [0:30] — ...\n"
        "  [1:00] — ...\n"
        "  [1:30] — ...\n"
        "  [2:00] — ...\n"
        "  [2:30] — ...\n"
        "  [3:00] — ...\n"
        "  Mark [WOW MOMENT] at the exact timestamp.\n"
        "  Mark [MULTILINGUAL MOMENT] where language switching is shown.\n"
        "  Mark [OFFLINE MOMENT] where load-shedding resilience is shown.\n\n"
        "JUDGE SCORING ANTICIPATION:\n"
        "  Innovation: what specific thing will make judges say 'I have never seen this'\n"
        "  Real-world impact: what specific moment proves this solves a real SA problem\n"
        "  Technical execution: what shows the AI is doing real work, not faked\n"
        "  AI-native: what proves AI is the engine, not a feature\n"
        "  Demo clarity: what makes this impossible to misunderstand\n\n"
        "DEMO FAILURE CONTINGENCY:\n"
        "  If the webcam fails: what is the fallback demo path\n"
        "  If the internet drops: what still works\n"
        "  If the live tremor demo is too subtle: how to make it visible\n"
    ),
    expected_output=(
        "10-second wow moment described frame by frame. Opening 30 seconds in exact spoken words. "
        "Full timestamped video script with WOW/MULTILINGUAL/OFFLINE markers. "
        "Judge scoring anticipation. Demo failure contingencies."
    ),
    agent=agent_demo_director,
    context=[task_visionary, task_clinical, task_sensor_architect, task_sa_employment],
)


# ═══════════════════════════════════════════════════════════
# AGENT 6 — THE DEVIL'S ADVOCATE
# Stress-tests the concept ruthlessly and forces
# the team to confront every weakness
# ═══════════════════════════════════════════════════════════
agent_devils_advocate = Agent(
    role="Ruthless Technical and Ethical Devil's Advocate",
    goal=(
        "Find every weakness, ethical risk, technical failure mode, and "
        "judge objection in the winning concept — then provide the exact "
        "counter-argument or mitigation for each one."
    ),
    backstory=(
        "You are the person every startup founder hates in the room. "
        "You have watched 200 hackathon teams fail because they fell in love "
        "with their own idea and stopped seeing its weaknesses. "
        "You ask the questions no one wants to ask: "
        "'What if the webcam can't track dark skin tones in low light?' "
        "'What if the tremor filter makes the mouse feel laggy and the user hates it?' "
        "'What if a locked-in user blinks involuntarily and triggers an unwanted click?' "
        "'Is eye tracking without consent an invasion of privacy?' "
        "'Can a 72-hour team actually ship a real-time multi-sensor system that works?' "
        "You are not trying to kill the idea. You are trying to make it bulletproof. "
        "For every weakness you name, you also provide the exact fix or counter-argument "
        "that the team can use when a judge challenges them."
    ),
    tools=[],
    llm=llm_creative,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_devils_advocate = Task(
    description=(
        f"{HACKATHON_CONTEXT}\n\n"
        "YOUR TASK:\n"
        "Stress-test the winning concept. Find every weakness. Provide every fix.\n\n"
        "ATTACK VECTORS TO COVER:\n\n"
        "1. TECHNICAL FAILURES:\n"
        "   - MediaPipe face tracking: what fails in low light, with glasses, dark skin tones\n"
        "   - Webcam latency: is 30fps fast enough for locked-in blink input?\n"
        "   - Tremor filter: does Kalman smoothing introduce perceptible lag?\n"
        "   - Keyboard hook: does pynput conflict with Windows UAC or antivirus?\n"
        "   - whisper offline: is whisper-tiny accurate enough for SA accents?\n\n"
        "2. USER EXPERIENCE FAILURES:\n"
        "   - False positive clicks from involuntary blinks\n"
        "   - Eye gaze fatigue after 20 minutes\n"
        "   - Tremor filter fighting intentional fast movements\n"
        "   - Cognitive overload from too many simultaneous adaptations\n\n"
        "3. ETHICAL AND PRIVACY RISKS:\n"
        "   - Continuous webcam surveillance of user's face and eyes\n"
        "   - Storing user disability profiles locally — what if device is stolen?\n"
        "   - Risk of the system misidentifying a disability and applying wrong adaptations\n\n"
        "4. HACKATHON EXECUTION RISKS:\n"
        "   - Is 72 hours realistic for a multi-sensor real-time system?\n"
        "   - What is the minimum viable version that still wins?\n"
        "   - What must be cut to ship something that works?\n\n"
        "5. JUDGE OBJECTIONS:\n"
        "   - 'This already exists in Windows accessibility settings'\n"
        "   - 'This only works on high-end laptops'\n"
        "   - 'A disabled person helped design this?'\n\n"
        "For EVERY weakness: name it clearly, then give the EXACT counter-argument or fix.\n"
        "End with: THE MINIMUM VIABLE DEMO — the smallest version that still wins.\n"
    ),
    expected_output=(
        "All attack vectors addressed with specific weaknesses and exact fixes. "
        "Minimum viable demo defined clearly."
    ),
    agent=agent_devils_advocate,
    context=[task_visionary, task_clinical, task_sensor_architect, task_sa_employment, task_demo_director],
)


# ═══════════════════════════════════════════════════════════
# AGENT 7 — THE MASTER BRIEF WRITER
# Synthesises everything into the definitive project_brief.md
# ═══════════════════════════════════════════════════════════
agent_brief_writer = Agent(
    role="Master Product Brief Architect",
    goal=(
        "Synthesise all 6 agent outputs into one definitive, locked project brief "
        "that a Phase 2 build crew of specialist agents can execute immediately — "
        "no ambiguity, no placeholders, no questions unanswered."
    ),
    backstory=(
        "You are a senior product architect who has written briefs for products used "
        "by millions of people. Your briefs are legendary in the industry. Engineers "
        "say: 'I did not need to ask a single question — it was all there.' "
        "You write for the engineer reading this at 2am during a build sprint. "
        "Every word earns its place. You are obsessive about specificity. "
        "Not 'eye tracking' but 'MediaPipe FaceMesh iris landmarks 468-473, "
        "sampled at 30fps, smoothed with exponential moving average alpha=0.3.' "
        "Not 'tremor compensation' but 'Kalman filter with process noise Q=0.01, "
        "measurement noise R=0.1, applied to raw mouse X/Y coordinates via pynput.' "
        "You never write TBD. You never leave a placeholder. "
        "You incorporate all clinical corrections, all technical risk mitigations, "
        "all demo strategies, and all devil's advocate fixes into one coherent document "
        "that is both inspiring and immediately executable."
    ),
    tools=[],
    llm=llm_precise,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

task_brief_writer = Task(
    description=(
        f"{HACKATHON_CONTEXT}\n\n"
        "YOUR TASK:\n"
        "Synthesise ALL previous agent outputs into the definitive project brief.\n"
        "This is the single source of truth for the Phase 2 build crew.\n\n"
        "WRITE ALL 14 SECTIONS — ZERO PLACEHOLDERS, ZERO TBD:\n\n"
        "1.  APP NAME & TAGLINE\n"
        "    One name. One line that says exactly what it does and who it's for.\n\n"
        "2.  VISION STATEMENT\n"
        "    3 sentences. The big idea. Why this matters. Why now.\n\n"
        "3.  PROBLEM STATEMENT\n"
        "    2 sentences. SA-specific pain. Scale in numbers.\n\n"
        "4.  SOLUTION OVERVIEW\n"
        "    4 sentences. What it is. What it does. How AI is the engine. What makes it different.\n\n"
        "5.  ALL 5 FOCUS AREAS — HOW EACH IS SERVED\n"
        "    For each: exact feature + exact technical mechanism + clinical basis.\n\n"
        "6.  SENSOR INTEGRATION MAP\n"
        "    For each sensor: exact library + exact model/algorithm + exact output + how used.\n"
        "    Webcam / Keyboard / Mouse / Microphone / Screen / TTS.\n\n"
        "7.  CORE FEATURES (exactly 6)\n"
        "    Each: Name + what it does + exact tech stack + clinical rationale.\n\n"
        "8.  AI LEARNING LOOP\n"
        "    What user data is collected. How stored. How fast it adapts. What improves.\n"
        "    Exact data structures. Exact update frequency.\n\n"
        "9.  FULL TECH STACK\n"
        "    EVERY library, model, API. No exceptions.\n"
        "    Format: Category: library/model — exact version — exact purpose.\n\n"
        "10. USER FLOW\n"
        "    Cold launch to completed task. Every step. 3 parallel flows:\n"
        "    Flow A: Parkinson's user composing an email\n"
        "    Flow B: Locked-in user navigating a SASSA application\n"
        "    Flow C: Blind + cognitive disability user in a job interview on Teams\n\n"
        "11. OFFLINE / LOAD-SHEDDING STRATEGY\n"
        "    Exactly what works offline. What model runs on CPU. What degrades.\n"
        "    Exact fallback message for each degraded feature.\n\n"
        "12. MULTILINGUAL SUPPORT\n"
        "    EN/ZU/ST/AF. gTTS codes. What is translated. What stays English and why.\n\n"
        "13. DEMO VIDEO SCRIPT\n"
        "    Full timestamped script from Agent 5. WOW/MULTILINGUAL/OFFLINE moments marked.\n"
        "    Opening human story in exact spoken words.\n\n"
        "14. WHAT NOT TO BUILD\n"
        "    5 specific time-wasters the build crew must not touch in 72 hours.\n"
        "    Include the minimum viable demo definition from Agent 6.\n\n"
        "OUTPUT FORMAT: Valid markdown. File: project_brief.md\n"
    ),
    expected_output=(
        "Complete project_brief.md in valid markdown. All 14 sections. "
        "Every field specific, actionable, unambiguous. Zero placeholders. "
        "Ready for immediate execution by the Phase 2 build crew."
    ),
    agent=agent_brief_writer,
    context=[
        task_visionary,
        task_clinical,
        task_sensor_architect,
        task_sa_employment,
        task_demo_director,
        task_devils_advocate,
    ],
    output_file="project_brief.md",
)


# ═══════════════════════════════════════════════════════════
# ASSEMBLE THE CREW
# ═══════════════════════════════════════════════════════════
brainstorm_crew = Crew(
    agents=[
        agent_visionary,
        agent_clinical,
        agent_sensor_architect,
        agent_sa_employment,
        agent_demo_director,
        agent_devils_advocate,
        agent_brief_writer,
    ],
    tasks=[
        task_visionary,
        task_clinical,
        task_sensor_architect,
        task_sa_employment,
        task_demo_director,
        task_devils_advocate,
        task_brief_writer,
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
    print("  ISAZI HACKATHON — PHASE 1: BRAINSTORM CREW V2")
    print("  UNIVERSAL ADAPTIVE LAYER EDITION")
    print(f"  Model   : Azure OpenAI GPT-4o")
    print(f"  Deploy  : {AZURE_DEPLOYMENT}")
    print(f"  Endpoint: {AZURE_ENDPOINT}")
    print("  Agents  : 7  |  Process : Sequential")
    print("  ETA     : 10 – 20 minutes")
    print("=" * 60 + "\n")

    result = brainstorm_crew.kickoff()

    print("\n" + "=" * 60)
    print("  PHASE 1 V2 COMPLETE")
    print("  Output saved to: project_brief.md")
    print("")
    print("  Read the brief. If the idea is right,")
    print("  run:  python phase2_build.py")
    print("=" * 60 + "\n")

    print(result)
