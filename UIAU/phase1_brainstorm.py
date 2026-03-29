"""
=============================================================
ISAZI AI ACCESSIBILITY HACKATHON
Phase 1 — Brainstorm Crew
Azure OpenAI GPT-4o + Serper Edition
=============================================================
5 agents. Sequential process.
Output: project_brief.md (hand-off to Phase 2 build crew)

SETUP:
  pip install crewai crewai-tools langchain-openai openai python-dotenv

.env file needs:
  AZURE_OPENAI_API_KEY=your_azure_key
  AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
  AZURE_OPENAI_DEPLOYMENT=your_deployment_name   (e.g. gpt-4o)
  AZURE_OPENAI_API_VERSION=2024-02-15-preview
  SERPER_API_KEY=your_serper_key

RUN:
  python phase1_brainstorm.py
=============================================================
"""

import os
from dotenv import load_dotenv

from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool

load_dotenv()
os.environ["CREWAI_AZURE_NATIVE"] = "false"
# ─────────────────────────────────────────────────────────
# AZURE OPENAI CONFIG
# Pull everything from .env — nothing hardcoded
# ─────────────────────────────────────────────────────────
AZURE_API_KEY     = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT    = os.getenv("AZURE_OPENAI_ENDPOINT")      # https://myresource.openai.azure.com/
AZURE_DEPLOYMENT  = os.getenv("AZURE_OPENAI_DEPLOYMENT")    # e.g. gpt-4o
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

# Fail fast with clear messages if anything is missing
for var, val in [
    ("AZURE_OPENAI_API_KEY",    AZURE_API_KEY),
    ("AZURE_OPENAI_ENDPOINT",   AZURE_ENDPOINT),
    ("AZURE_OPENAI_DEPLOYMENT", AZURE_DEPLOYMENT),
]:
    if not val:
        raise ValueError(
            f"\n  Missing environment variable: {var}\n"
            f"  Add it to your .env file and try again.\n"
        )

# ── Creative LLM — agents 1 to 4 (brainstorm) ────────────
llm_creative = LLM(
    model=f"azure/{AZURE_DEPLOYMENT}",
    api_key=AZURE_API_KEY,
    base_url=AZURE_ENDPOINT,
    api_version=AZURE_API_VERSION,
    temperature=0.8,      # high creativity for ideation phase
    max_tokens=4096,
)

# ── Precise LLM — agent 5 (brief writer) ─────────────────
llm_precise = LLM(
    model=f"azure/{AZURE_DEPLOYMENT}",
    api_key=AZURE_API_KEY,
    base_url=AZURE_ENDPOINT,
    api_version=AZURE_API_VERSION,
    temperature=0.2,      # structured, deterministic output
    max_tokens=8096,
)

# ─────────────────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────────────────
search_tool = SerperDevTool(
    api_key=os.getenv("SERPER_API_KEY"),
    n_results=5,
)

# ─────────────────────────────────────────────────────────
# HACKATHON CONTEXT — injected into every agent task
# ─────────────────────────────────────────────────────────
HACKATHON_CONTEXT = """
HACKATHON : Isazi AI Accessibility Hackathon
ORGANISER : Isazi Consulting (Pty) Ltd — isazi.ai
PARTNER   : UNISA
PRIZE POOL: R52,500 total cash prizes
BUILD TIME: 72 hours (Friday 18:00 → Sunday 17:00)
SUBMISSION: 2–10 minute demo video of a working prototype
JUDGING   : Innovation · Real-world impact · Technical execution · AI-native · Demo clarity

FOCUS AREAS (covering more areas = stronger submission):
  1. Visual disability     — blindness, low vision, colour blindness
  2. Mobility disability   — limited motor control, wheelchair users, tremors
  3. Hearing & speech      — deafness, hard of hearing, speech impairments
  4. Cognitive disability  — dyslexia, ADHD, autism spectrum, memory impairments
  5. Employment barriers   — disabled people struggling to find or keep jobs

SOUTH AFRICA SPECIFIC CONSTRAINTS:
  - Load-shedding up to 8 hours daily — offline resilience is non-negotiable
  - 11 official languages — isiZulu, isiXhosa, Afrikaans, Sesotho most spoken
  - Most users are on basic Android phones with limited mobile data
  - Key government systems: SASSA disability grants, UIF
  - 1 in 3 disabled adults in SA is unemployed (Stats SA)
  - Very low assistive tech ownership — the smartphone is the primary device
"""


# ═══════════════════════════════════════════════════════════
# AGENT 1 — THE PROVOCATEUR
# Generates 5 wild, hybrid, multi-focus-area ideas
# ═══════════════════════════════════════════════════════════
agent_provocateur = Agent(
    role="Radical Innovation Provocateur",
    goal=(
        "Generate 5 breakthrough accessibility app concepts for the Isazi hackathon "
        "that combine multiple disability focus areas into one hybrid solution — "
        "ideas that no other team will think of."
    ),
    backstory=(
        "You are a contrarian design researcher who has spent 10 years studying what "
        "assistive technology gets wrong. You have seen a thousand screen-reader apps "
        "and big-button UIs and they disgust you. You believe disabled people deserve "
        "technology that is powerful, intelligent, and treats them as whole humans — "
        "not a compliance checklist. You only propose ideas that make judges lean "
        "forward and say 'I have never seen that before.' You think in terms of the "
        "single 10-second moment that wins a room. Obvious solutions are your enemy."
    ),
    tools=[search_tool],
    llm=llm_creative,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_provocateur = Task(
    description=(
        f"{HACKATHON_CONTEXT}\n\n"
        "YOUR TASK:\n"
        "Generate exactly 5 accessibility app ideas for this hackathon.\n\n"
        "EVERY idea MUST:\n"
        "  - Combine at least 3 of the 5 focus areas in ONE unified app (not bolt-ons)\n"
        "  - Be buildable as a working prototype in 72 hours using free AI tools\n"
        "  - Have ONE demo moment that wins the room in under 10 seconds\n"
        "  - Work during South African load-shedding (offline or cached fallback)\n"
        "  - Be something no other hackathon team would think of\n\n"
        "HARD REJECT any idea that is:\n"
        "  - Just a screen reader\n"
        "  - Just a speech-to-text transcription tool\n"
        "  - Just a big-button UI\n"
        "  - A feature that already exists in VoiceOver, TalkBack, or Be My Eyes\n\n"
        "FORMAT each idea EXACTLY like this (no deviation):\n\n"
        "IDEA [N]: [Name]\n"
        "One-line description: ...\n"
        "Focus areas covered: ...\n"
        "The 10-second demo moment: ...\n"
        "Why no other team will build this: ...\n"
        "Core AI magic: (exact model or capability that makes this possible)\n"
    ),
    expected_output=(
        "Exactly 5 numbered innovation concepts. Each formatted with: name, "
        "one-line description, focus areas covered, 10-second demo moment, "
        "why it is unique, and the core AI capability powering it."
    ),
    agent=agent_provocateur,
)


# ═══════════════════════════════════════════════════════════
# AGENT 2 — THE SA REALITY CHECKER
# Scores and filters ideas against SA-specific constraints
# ═══════════════════════════════════════════════════════════
agent_sa_checker = Agent(
    role="South African Disability Context Specialist",
    goal=(
        "Score and filter the 5 ideas against real South African constraints — "
        "load-shedding, multilingual needs, government system integration, and the "
        "actual lived experience of disabled South Africans — eliminating anything "
        "that would fail in the field."
    ),
    backstory=(
        "You have worked with disability NGOs across Johannesburg, Cape Town, Durban, "
        "and rural KwaZulu-Natal for 12 years. You ran digital access programmes for "
        "the Deaf Federation of South Africa and consulted for SASSA on grant system "
        "accessibility. You have watched 100 well-meaning tech solutions fail in SA "
        "because they ignored load-shedding, assumed fast data, or were English-only. "
        "You score ideas ruthlessly. You have zero patience for things that work in "
        "a Cape Town co-working space but break in Soweto during stage 6."
    ),
    tools=[search_tool],
    llm=llm_creative,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_sa_checker = Task(
    description=(
        f"{HACKATHON_CONTEXT}\n\n"
        "YOUR TASK:\n"
        "Score each of the 5 ideas across 5 SA-specific criteria (each out of 10):\n\n"
        "  1. OFFLINE RESILIENCE (0-10)\n"
        "     Can core features run during load-shedding? Is there caching? Local fallback models?\n\n"
        "  2. MULTILINGUAL SUPPORT (0-10)\n"
        "     Is it realistic to support isiZulu, Sesotho, Afrikaans, English within 72 hours?\n\n"
        "  3. SA DISABILITY ALIGNMENT (0-10)\n"
        "     Does it address a real SA-specific pain — not just a generic global problem?\n\n"
        "  4. GOVERNMENT SYSTEM INTEGRATION (0-10)\n"
        "     Can it connect with SASSA, UIF, or another SA disability system — even partially?\n\n"
        "  5. MOBILE FIRST (0-10)\n"
        "     Does it work on a basic Android phone with limited data and no laptop?\n\n"
        "ELIMINATION RULES (hard, non-negotiable):\n"
        "  - ELIMINATE if total score is below 30/50\n"
        "  - ELIMINATE if Offline Resilience score is 0 (load-shedding kills it)\n\n"
        "For each surviving idea, add ONE specific improvement suggestion.\n"
        "Rank survivors from highest to lowest total score.\n\n"
        "FORMAT each idea as:\n"
        "IDEA [N]: [Name] — TOTAL: [X]/50 — STATUS: SURVIVES / ELIMINATED\n"
        "Scores: Offline [X] | Multilingual [X] | SA Alignment [X] | Gov [X] | Mobile [X]\n"
        "Reason: (2 sentences on why it scores this way)\n"
        "Improvement: (one specific change that would make it stronger)\n"
    ),
    expected_output=(
        "All 5 ideas scored across 5 criteria with totals, SURVIVES/ELIMINATED status, "
        "improvement suggestions for survivors, and survivors ranked strongest to weakest."
    ),
    agent=agent_sa_checker,
    context=[task_provocateur],
)


# ═══════════════════════════════════════════════════════════
# AGENT 3 — THE TECHNICAL FEASIBILITY JUDGE
# Maps exact free tech stack, selects top 2 buildable ideas
# ═══════════════════════════════════════════════════════════
agent_tech_judge = Agent(
    role="AI Prototyping Architect",
    goal=(
        "Assess technical feasibility of each surviving idea and map the exact "
        "free-tier tech stack needed to ship a working demo in 72 hours. "
        "Select the top 2 most buildable ideas."
    ),
    backstory=(
        "You have shipped 25 AI hackathon projects and won 6 of them. "
        "You have a brutal internal clock — you know exactly what takes 2 hours, "
        "what takes 8 hours, and what explodes at 11pm on Saturday and kills a demo. "
        "You have shipped under extreme pressure using Azure OpenAI GPT-4o, Whisper, "
        "gTTS, pyttsx3, OpenCV, HuggingFace transformers, Streamlit, Flask, FastAPI. "
        "You know every free tier rate limit by heart. You have never over-promised "
        "what a small team can build in a weekend."
    ),
    tools=[],
    llm=llm_creative,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_tech_judge = Task(
    description=(
        f"{HACKATHON_CONTEXT}\n\n"
        "YOUR TASK:\n"
        "For each surviving idea produce a full technical feasibility report.\n\n"
        "TECH STACK MAPPING (be specific — no vague 'use AI here'):\n"
        "  - Primary LLM  : Azure OpenAI GPT-4o via AzureChatOpenAI (LangChain)\n"
        "  - STT          : OpenAI Whisper (whisper-small or base for speed)\n"
        "  - TTS          : gTTS or pyttsx3 (offline)\n"
        "  - Vision       : OpenCV or PIL (if needed)\n"
        "  - Offline AI   : HuggingFace pipeline (name the exact model)\n"
        "  - Framework    : Streamlit / Flask / FastAPI — choose one and justify\n"
        "  - Storage      : SQLite / JSON files / in-memory — choose and justify\n"
        "  - Offline cache: joblib / diskcache / shelve — choose and justify\n"
        "  - Note any free tier limits that could hit during a live demo\n\n"
        "TIME ESTIMATE:\n"
        "  Break the build into hours per feature.\n"
        "  TOTAL must be 60 hours or under (12 hours reserved for polish + video).\n\n"
        "DEMO PATH:\n"
        "  Exactly what the 10-minute video shows — screen by screen, feature by feature.\n\n"
        "TOP 3 RISKS:\n"
        "  What could break this demo on Sunday, and the exact prevention strategy.\n\n"
        "BUILD CONFIDENCE: HIGH / MEDIUM / LOW with one-line justification.\n\n"
        "FORMAT per idea:\n"
        "IDEA [N]: [Name]\n"
        "Tech Stack: ...\n"
        "Hour breakdown: ...\n"
        "Demo path: ...\n"
        "Top 3 risks: ...\n"
        "Build confidence: HIGH / MEDIUM / LOW — [reason]\n\n"
        "FINAL SELECTION:\n"
        "TOP 2: [Idea X] and [Idea Y]\n"
        "Reasoning: (why these two beat the others)\n"
    ),
    expected_output=(
        "Full technical feasibility report for each surviving idea including exact "
        "tech stack, hour breakdown, demo path, top 3 risks, build confidence rating, "
        "and a clear selection of the top 2 most buildable ideas with reasoning."
    ),
    agent=agent_tech_judge,
    context=[task_provocateur, task_sa_checker],
)


# ═══════════════════════════════════════════════════════════
# AGENT 4 — THE JUDGE WHISPERER
# Picks ONE winner, crafts full pitch + demo script
# ═══════════════════════════════════════════════════════════
agent_judge_whisperer = Agent(
    role="Hackathon Judge Psychology Expert",
    goal=(
        "Select the single strongest idea from the top 2 and craft the complete "
        "pitch package — human story, 30-second pitch in exact spoken words, "
        "10-second wow moment, and timestamped demo flow — designed to win the "
        "Isazi judging panel."
    ),
    backstory=(
        "You have judged 35 hackathons across Africa and Europe and mentored "
        "winning teams at 18 more. You know exactly what happens inside a judge's "
        "head during a demo — what makes them lean forward, what makes them check "
        "their phone. You think in story, human impact, and the single moment that "
        "makes a room go quiet. You have watched technically brilliant projects lose "
        "because they opened with an architecture diagram instead of a human story. "
        "You always open with the person, never the product. "
        "You understand that Isazi's mission is AI-native — AI must be the engine, "
        "not a feature bolted on to look impressive."
    ),
    tools=[],
    llm=llm_creative,
    verbose=True,
    allow_delegation=False,
    max_iter=3,
)

task_judge_whisperer = Task(
    description=(
        f"{HACKATHON_CONTEXT}\n\n"
        "YOUR TASK:\n"
        "Select ONE winner from the top 2 feasibility-approved ideas.\n"
        "Score each idea on:\n"
        "  - Innovation: genuinely new, not seen before\n"
        "  - Human impact clarity: can a judge feel the pain it solves in 5 seconds?\n"
        "  - Live demo wow factor: is the 10-second moment undeniable?\n"
        "  - Isazi AI-native fit: is AI the engine, not the decoration?\n"
        "  - Uniqueness vs other teams: would every other team pick something safer?\n\n"
        "THEN WRITE THE FULL PITCH PACKAGE:\n\n"
        "WINNER: [Name]\n"
        "Why this beats the other: (3 sentences, concrete not vague)\n\n"
        "THE HUMAN STORY (spoken aloud before touching the app — 30 seconds):\n"
        "  Start with a specific named person living in South Africa.\n"
        "  Describe their daily pain in plain, human language.\n"
        "  NO jargon. NO 'we built an AI solution'. NO statistics to open.\n"
        "  Pure story. Example: 'Thabo is 41. He has been deaf since birth...'\n\n"
        "30-SECOND PITCH (exact words, spoken after the human story):\n"
        "  Introduce the app. What it does. Why AI makes it possible now.\n"
        "  Write it to be spoken — natural rhythm, no bullet points.\n\n"
        "THE 10-SECOND WOW MOMENT:\n"
        "  Describe precisely what appears on screen at this moment.\n"
        "  What does the presenter click? What does the audience see?\n"
        "  Why does the room go quiet?\n\n"
        "3 THINGS JUDGES WILL LOVE:\n"
        "  Be specific. Not 'it is innovative'. Specific and concrete.\n\n"
        "1 WEAKNESS AND THE COUNTER-MOVE:\n"
        "  Name the real weakness honestly. Then give the exact counter argument.\n\n"
        "TIMESTAMPED DEMO FLOW (for the 2–10 minute submission video):\n"
        "  [0:00] ... [0:30] ... [1:00] ... [2:00] ... etc.\n"
        "  Each timestamp: what is shown on screen + what the presenter says.\n"
    ),
    expected_output=(
        "Winner selection with score rationale. Human story in exact spoken words. "
        "30-second pitch script. 10-second wow moment. 3 specific judge appeals. "
        "1 honest weakness + counter-move. Timestamped demo flow for the video."
    ),
    agent=agent_judge_whisperer,
    context=[task_provocateur, task_sa_checker, task_tech_judge],
)


# ═══════════════════════════════════════════════════════════
# AGENT 5 — THE BRIEF WRITER
# Locks everything into project_brief.md for Phase 2
# ═══════════════════════════════════════════════════════════
agent_brief_writer = Agent(
    role="Product Brief Architect",
    goal=(
        "Synthesise all brainstorm outputs into one locked, structured project brief "
        "that the Phase 2 build crew can execute immediately without asking any questions."
    ),
    backstory=(
        "You are a senior product manager who has written briefs for 60+ AI products "
        "shipped in production. Your briefs are legendary. Engineers who receive them "
        "say: 'I did not need to ask a single question — it was all there.' "
        "You are obsessive about specificity. Not 'support multiple languages' but "
        "'support EN, ZU, ST, AF using gTTS language codes en, zu, st, af and "
        "pyttsx3 as the offline fallback.' You write for the engineer reading this "
        "at 2am during a hackathon build sprint. Every word earns its place. "
        "You never leave a placeholder. You never write TBD."
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
        "Synthesise all previous agent outputs into a locked project brief.\n"
        "This is the single source of truth for the Phase 2 build crew.\n"
        "Every agent in Phase 2 reads this document first and only this document.\n\n"
        "WRITE ALL 12 SECTIONS — NO PLACEHOLDERS, NO TBD, NO VAGUE LANGUAGE:\n\n"
        "1.  APP NAME & TAGLINE\n"
        "    One name. One memorable line that says exactly what it does.\n\n"
        "2.  PROBLEM STATEMENT\n"
        "    Exactly 2 sentences. SA-specific pain + the scale of it in numbers.\n\n"
        "3.  SOLUTION OVERVIEW\n"
        "    Exactly 3 sentences. What it does. How AI is the engine. What makes it different.\n\n"
        "4.  FOCUS AREAS COVERED\n"
        "    Which of the 5 Isazi focus areas. One sentence each on HOW it addresses each one.\n\n"
        "5.  CORE FEATURES (exactly 5)\n"
        "    Each feature: Name + 2-sentence description of what it does + which AI model powers it.\n\n"
        "6.  FULL TECH STACK\n"
        "    EVERY library, API, and model. No exceptions.\n"
        "    Format: Category: tool/library/model — exact purpose in this app\n"
        "    Primary LLM: Azure OpenAI GPT-4o (AzureChatOpenAI via LangChain)\n"
        "    Include: STT model, TTS library, offline fallback model name, framework,\n"
        "    caching library, storage, any HuggingFace model names in full.\n\n"
        "7.  USER FLOW\n"
        "    From cold app launch to completed task. Every screen. Every tap.\n"
        "    Number each step. No steps skipped.\n\n"
        "8.  OFFLINE / LOAD-SHEDDING STRATEGY\n"
        "    What exact features work without internet.\n"
        "    What is cached and with which library.\n"
        "    What degrades gracefully and what the fallback message says.\n\n"
        "9.  MULTILINGUAL SUPPORT\n"
        "    Languages: EN, ZU, ST, AF — confirm which components are translated.\n"
        "    List which gTTS language codes are used per language.\n"
        "    List what remains English-only and why.\n\n"
        "10. DEMO VIDEO SCRIPT OUTLINE\n"
        "    Timestamped. What is on screen. What the presenter says.\n"
        "    Mark clearly: [WOW MOMENT] at the right timestamp.\n\n"
        "11. SUCCESS CRITERIA\n"
        "    What a passing demo looks like — specific and checkable.\n"
        "    What must work for this to be a valid hackathon submission.\n\n"
        "12. WHAT NOT TO BUILD\n"
        "    3 specific things the build crew must NOT spend time on in 72 hours.\n"
        "    Be blunt. These are time-wasters that will kill the submission.\n\n"
        "OUTPUT FORMAT: Valid markdown. Save as project_brief.md\n"
    ),
    expected_output=(
        "A complete project_brief.md in valid markdown. All 12 sections present. "
        "Every field filled with specific, actionable, unambiguous content. "
        "Zero placeholders. Zero vague language. "
        "Ready for the Phase 2 build crew to execute immediately."
    ),
    agent=agent_brief_writer,
    context=[
        task_provocateur,
        task_sa_checker,
        task_tech_judge,
        task_judge_whisperer,
    ],
    output_file="project_brief.md",
)


# ═══════════════════════════════════════════════════════════
# ASSEMBLE THE CREW
# Sequential — each agent reads all previous agent outputs
# ═══════════════════════════════════════════════════════════
brainstorm_crew = Crew(
    agents=[
        agent_provocateur,
        agent_sa_checker,
        agent_tech_judge,
        agent_judge_whisperer,
        agent_brief_writer,
    ],
    tasks=[
        task_provocateur,
        task_sa_checker,
        task_tech_judge,
        task_judge_whisperer,
        task_brief_writer,
    ],
    process=Process.sequential,
    verbose=True,
    memory=False,   # flip to True if you add a vector store (Chroma etc.)
)


# ═══════════════════════════════════════════════════════════
# RUN
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ISAZI HACKATHON — PHASE 1: BRAINSTORM CREW")
    print(f"  Model   : Azure OpenAI GPT-4o")
    print(f"  Deploy  : {AZURE_DEPLOYMENT}")
    print(f"  Endpoint: {AZURE_ENDPOINT}")
    print("  Agents  : 5  |  Process : Sequential")
    print("  ETA     : 5 – 10 minutes")
    print("=" * 60 + "\n")

    result = brainstorm_crew.kickoff()

    print("\n" + "=" * 60)
    print("  PHASE 1 COMPLETE")
    print("  Output saved to: project_brief.md")
    print("")
    print("  Read the brief. If the idea is right,")
    print("  run:  python phase2_build.py")
    print("=" * 60 + "\n")

    print(result)
