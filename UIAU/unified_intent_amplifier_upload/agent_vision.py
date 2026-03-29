"""
agent_vision.py — Full screen understanding agent.
Knows WHAT is on screen, WHERE things are, and WHAT the user should do next.
Uses Azure Computer Vision + GPT-4o Vision. Fires callbacks on every insight.
"""
import os, time, threading, logging, base64
from io import BytesIO
logger = logging.getLogger(__name__)

try:
    import pyautogui
    from PIL import Image
    _OK = True
except ImportError:
    _OK = False

SCREEN_AGENT_PROMPT = """You are an expert accessibility AI with 20 years experience
helping people with Parkinson's disease, tremors, and motor disabilities use computers.
You are looking at a screenshot of their screen right now.

Analyse the screen and return a JSON object with these exact keys:
{
  "page_type": one of: job_listing, job_application_form, login_page, dashboard,
                       search_results, email, video_call, document, general,
                       success_screen, error_screen, sassa_form, uif_form,
  "site": the website or app name if visible,
  "stage": what stage of a task the user appears to be at (1-2 words),
  "primary_action": the single most important thing the user should do RIGHT NOW
                    (max 15 words, name the exact button or field),
  "form_fields": list of visible form field labels if this is a form (empty list if not),
  "buttons_visible": list of visible button/link names (max 6),
  "urgent": true if there is an error, warning, timeout, or required field unfilled,
  "tip": one warm encouraging sentence for a person with tremors using gaze control
}

Be specific. Name exact buttons. Be warm. Max 15 words for primary_action and tip.
Return ONLY the JSON object, no markdown, no explanation."""

class ScreenUnderstandingAgent:
    def __init__(self):
        self._running = False
        self._thread = None
        self._interval = 6.0
        self._last_understanding = {}
        self._lock = threading.Lock()

        self.on_understanding = None  # callback(understanding_dict)
        self.on_tip = None
        self.on_speak = None
        self.enabled = False

        self._vision_key = os.getenv("AZURE_AI_SERVICES_KEY", "")
        self._vision_endpoint = os.getenv("AZURE_AI_SERVICES_ENDPOINT", "")
        self._openai_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self._openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self._openai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        self._openai_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

    def understand_now(self) -> dict:
        if not _OK:
            return {}
        try:
            shot = pyautogui.screenshot()
            img = shot.resize((1024, 576))
            buf = BytesIO()
            img.save(buf, format="PNG")
            img_b64 = base64.b64encode(buf.getvalue()).decode()

            import httpx, json

            headers = {
                "api-key": self._openai_key,
                "Content-Type": "application/json",
            }
            body = {
                "model": self._openai_deployment,
                "messages": [
                    {"role": "system", "content": SCREEN_AGENT_PROMPT},
                    {"role": "user", "content": [
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/png;base64,{img_b64}",
                            "detail": "high"
                        }},
                        {"type": "text", "text": "What is on this screen? Return the JSON."}
                    ]}
                ],
                "max_tokens": 400,
                "temperature": 0,
            }
            url = (f"{self._openai_endpoint.rstrip('/')}/openai/deployments/"
                   f"{self._openai_deployment}/chat/completions"
                   f"?api-version={self._openai_version}")
            resp = httpx.post(url, headers=headers, json=body, timeout=15)
            if resp.status_code != 200:
                logger.warning("agent_vision %d: %s", resp.status_code, resp.text[:100])
                return {}
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            raw = raw.replace("```json","").replace("```","").strip()
            understanding = json.loads(raw)

            with self._lock:
                self._last_understanding = understanding

            if self.on_understanding:
                self.on_understanding(understanding)

            tip = understanding.get("primary_action", "")
            if tip:
                if self.on_tip:
                    self.on_tip(f"🧠 {tip}")
                if self.on_speak:
                    self.on_speak(tip)

            logger.info("Screen: %s | %s | %s",
                understanding.get("site","?"),
                understanding.get("page_type","?"),
                understanding.get("primary_action","")[:60])
            return understanding

        except Exception as exc:
            logger.warning("ScreenUnderstandingAgent error: %s", exc)
            return {}

    def get_last(self) -> dict:
        with self._lock:
            return dict(self._last_understanding)

    def _run(self):
        while self._running:
            if self.enabled:
                self.understand_now()
            time.sleep(self._interval)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="VisionAgent")
        self._thread.start()
        logger.info("ScreenUnderstandingAgent started")

    def stop(self):
        self._running = False

    def set_enabled(self, v: bool):
        self.enabled = v

screen_agent = ScreenUnderstandingAgent()
