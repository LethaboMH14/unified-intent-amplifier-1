"""
agent_team.py — Multi-agent PhD-level team for Unified Intent Amplifier.

Agents:
  CommanderAgent  — orchestrates all agents, synthesises final answer
  NavigatorAgent  — web navigation expert, SA job sites specialist
  FormFillerAgent — form extraction and auto-fill specialist
  VoiceAgent      — speech understanding and command correction specialist
  EmpathyAgent    — emotional support and adaptive strategy specialist
  IdeaAgent       — idea generation and next-step planning specialist

Usage:
  from agent_team import agent_team
  result = agent_team.run("help me apply for this job")
"""
import os, logging, threading
logger = logging.getLogger(__name__)

# httpx used directly in _ask() — no langchain needed

def _ask(system: str, user: str) -> str:
    """Call GPT-4o directly via httpx — avoids langchain URL construction issues."""
    api_key  = os.getenv("AZURE_OPENAI_API_KEY", "")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    deploy   = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    version  = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    if not api_key or not endpoint:
        return ""
    try:
        import httpx
        url = f"{endpoint}/openai/deployments/{deploy}/chat/completions?api-version={version}"
        body = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "max_tokens": 200,
            "temperature": 0.2,
        }
        resp = httpx.post(url,
                          headers={"api-key": api_key, "Content-Type": "application/json"},
                          json=body, timeout=12)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        logger.warning("agent_team LLM %d: %s", resp.status_code, resp.text[:80])
        return ""
    except Exception as exc:
        logger.warning("Agent LLM error: %s", exc)
        return ""

# ── Agent definitions ─────────────────────────────────────────────────────────

class NavigatorAgent:
    SYSTEM = """You are a navigation expert with 20 years experience helping
disabled South Africans use job sites. You know Careers24, PNet, LinkedIn,
Indeed, SASSA, UIF inside out. Given a goal and current screen context,
return the exact next navigation step in 1 sentence. Name the exact button,
link, or keyboard shortcut. No preamble."""

    def navigate(self, goal: str, screen_context: str) -> str:
        return _ask(self.SYSTEM, f"Goal: {goal}\nScreen: {screen_context}\nNext step?")

class FormFillerAgent:
    SYSTEM = """You are a form-filling expert. Given visible form fields and
a user profile, return a JSON object mapping field label → value to enter.
Only include fields you can see. Return ONLY JSON, no markdown."""

    USER_PROFILE = {
        "disability": "Parkinson's disease with tremors",
        "nationality": "South African",
        "looking_for": "employment",
        "accommodation_needed": "Yes — motor and speech accessibility support",
    }

    def extract_fields(self, screen_text: str) -> dict:
        import json
        raw = _ask(self.SYSTEM,
            f"Screen text: {screen_text[:600]}\n"
            f"User profile: {self.USER_PROFILE}\n"
            f"Return JSON field->value pairs:")
        try:
            return json.loads(raw.replace("```json","").replace("```","").strip())
        except Exception:
            return {}

class VoiceAgent:
    SYSTEM = """You are a speech recognition correction expert. The user has
Parkinson's and their speech may be slurred or quiet. Given a possibly garbled
transcription and the current screen context, determine the most likely intended
command. Return ONLY the corrected command, nothing else."""

    def correct_command(self, garbled: str, screen_context: str) -> str:
        return _ask(self.SYSTEM,
            f"Transcribed (may be wrong): '{garbled}'\n"
            f"Screen context: {screen_context}\n"
            f"Most likely intended command:")

class EmpathyAgent:
    SYSTEM = """You are a warm, patient accessibility coach. The user has
Parkinson's and may be frustrated. Given their situation, give ONE short
(max 12 words) encouraging message that also suggests the simplest next action.
Be warm, direct, never condescending."""

    def encourage(self, situation: str) -> str:
        return _ask(self.SYSTEM, f"Situation: {situation}")

class IdeaAgent:
    SYSTEM = """You are a strategic advisor helping a South African with
Parkinson's disease find employment and complete digital tasks. Given their
current screen and goal, generate exactly 3 concrete next-step ideas ranked
easiest first. Format as: 1. [idea] 2. [idea] 3. [idea]. Max 10 words each."""

    def generate_ideas(self, goal: str, screen_context: str) -> list[str]:
        raw = _ask(self.SYSTEM,
            f"Goal: {goal}\nScreen: {screen_context}\nGive 3 ideas:")
        ideas = []
        for line in raw.split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                ideas.append(line[2:].strip() if len(line) > 2 else line)
        return ideas[:3]

class CommanderAgent:
    """Orchestrates all agents. Entry point for the team."""
    SYSTEM = """You are the commander of an AI accessibility team helping a
South African with Parkinson's disease. You receive a user request and
context. You have these specialists available: Navigator, FormFiller,
Voice, Empathy, Idea. Decide which specialist(s) to use and synthesise
their outputs into ONE clear, actionable response. Max 2 sentences.
Be warm and specific."""

    def __init__(self):
        self.navigator  = NavigatorAgent()
        self.form_filler = FormFillerAgent()
        self.voice      = VoiceAgent()
        self.empathy    = EmpathyAgent()
        self.idea       = IdeaAgent()

    def run(self, user_request: str, screen_context: str = "",
             screen_understanding: dict = None) -> dict:
        """
        Main entry point. Returns dict with:
          response: str — what to say/show to user
          action: str   — machine-readable action type
          fields: dict  — if form filling, the field→value map
          ideas: list   — if idea generation requested
        """
        ctx = screen_context
        page = (screen_understanding or {}).get("page_type", "general")
        req = user_request.lower()

        result = {"response": "", "action": "speak", "fields": {}, "ideas": []}

        # Route to specialists based on request type
        if any(w in req for w in ["stuck", "what should", "idea", "help",
                                    "don't know", "lost", "confused"]):
            ideas = self.idea.generate_ideas(user_request, ctx)
            result["ideas"] = ideas
            result["action"] = "ideas"
            result["response"] = self.empathy.encourage(
                f"User said: {user_request}. Screen: {page}")
            if ideas:
                result["response"] += " Try: " + ideas[0]

        elif any(w in req for w in ["fill", "form", "apply", "submit",
                                      "complete", "application"]):
            fields = self.form_filler.extract_fields(ctx)
            result["fields"] = fields
            result["action"] = "fill_form"
            nav = self.navigator.navigate(user_request, ctx)
            result["response"] = nav or "I will fill in the form for you now."

        elif any(w in req for w in ["go to", "navigate", "open", "find",
                                      "search", "how do i get"]):
            nav = self.navigator.navigate(user_request, ctx)
            result["response"] = nav
            result["action"] = "navigate"

        elif any(w in req for w in ["frustrated", "tired", "hard",
                                      "difficult", "struggling", "cant"]):
            result["response"] = self.empathy.encourage(user_request)
            result["action"] = "encourage"

        else:
            # General question — commander synthesises
            result["response"] = _ask(self.SYSTEM,
                f"Request: {user_request}\nScreen: {ctx}\nPage: {page}")
            result["action"] = "speak"

        logger.info("AgentTeam: action=%s response='%s'",
                    result["action"], result["response"][:80])
        return result

# Singleton
agent_team_instance = CommanderAgent()

class AgentTeam:
    """Wrapper with async support and callbacks for main.py integration."""
    def __init__(self):
        self._commander = agent_team_instance
        self.on_tip = None
        self.on_speak = None
        self.ui_automation = None
        self._screen_agent = None

    def set_screen_agent(self, agent):
        self._screen_agent = agent

    def run_async(self, user_request: str):
        """Run the agent team in a background thread."""
        threading.Thread(
            target=self._run_and_dispatch,
            args=(user_request,),
            daemon=True,
            name="AgentTeam"
        ).start()

    def _run_and_dispatch(self, user_request: str):
        understanding = {}
        screen_text = ""
        if self._screen_agent:
            understanding = self._screen_agent.get_last()
            screen_text = str(understanding)

        result = self._commander.run(
            user_request,
            screen_context=screen_text,
            screen_understanding=understanding
        )

        if self.on_tip and result["response"]:
            self.on_tip(f"🤖 {result['response']}")
        if self.on_speak and result["response"]:
            self.on_speak(result["response"])

        # Dispatch actions
        if result["action"] == "fill_form" and self.ui_automation:
            if result["fields"]:
                self.ui_automation.fill_form(result["fields"])

        if result["action"] == "ideas" and result["ideas"]:
            for i, idea in enumerate(result["ideas"], 1):
                if self.on_tip:
                    self.on_tip(f"💡 Idea {i}: {idea}")

agent_team = AgentTeam()
