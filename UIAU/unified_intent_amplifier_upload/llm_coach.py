"""
llm_coach.py — Adaptive coaching prompts via Azure OpenAI GPT-4o.
Falls back to pre-written offline tips if internet/API is unavailable.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Offline fallback tips ───────────────────────────────────────────────────
OFFLINE_TIPS = {
    "tremor": [
        "Try resting your wrist on the desk while moving the mouse.",
        "Use keyboard shortcuts instead of the mouse where possible.",
        "Take short breaks every 20 minutes to reduce fatigue.",
    ],
    "gaze": [
        "Look slightly above your target to account for gaze drift.",
        "Ensure your screen is at eye level for best tracking.",
        "Blink slowly and deliberately to trigger a click.",
    ],
    "typing": [
        "Type at a comfortable pace — the system will correct errors.",
        "Use voice input when typing feels difficult.",
        "Try larger keyboard layouts for easier key targeting.",
    ],
    "general": [
        "All features work offline — no internet needed.",
        "Your settings are saved automatically between sessions.",
        "Press F8 anytime to toggle all assistive features on or off.",
    ],
}

_tip_index: dict[str, int] = {k: 0 for k in OFFLINE_TIPS}


def _offline_tip(category: str = "general") -> str:
    """Return the next offline tip for a given category (cycles through list)."""
    tips = OFFLINE_TIPS.get(category, OFFLINE_TIPS["general"])
    idx = _tip_index.get(category, 0)
    tip = tips[idx % len(tips)]
    _tip_index[category] = idx + 1
    return tip


def get_coaching_tip(context: str = "", category: str = "general") -> str:
    """
    Return an adaptive coaching tip.

    Tries Azure OpenAI first; falls back to offline tips if unavailable.

    Args:
        context: Brief description of what the user is currently doing.
        category: One of 'tremor', 'gaze', 'typing', 'general'.

    Returns:
        A short coaching tip string.
    """
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")

    if not all([api_key, endpoint, deployment]):
        logger.debug("Azure credentials missing — using offline tip")
        return _offline_tip(category)

    try:
        # Import here so missing langchain doesn't crash the app
        from langchain_openai import AzureChatOpenAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from config import LLM_MAX_TOKENS, LLM_TEMPERATURE, LLM_TIMEOUT_S

        llm = AzureChatOpenAI(
            azure_deployment=deployment,
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            request_timeout=LLM_TIMEOUT_S,
        )
        messages = [
            SystemMessage(content=(
                "You are an accessibility coach helping users with motor, visual, "
                "and cognitive disabilities use their laptop more effectively. "
                "Give one short, practical, encouraging tip in 1-2 sentences. "
                "No jargon. Be warm and specific."
            )),
            HumanMessage(content=f"Category: {category}. Context: {context or 'general use'}"),
        ]
        response = llm.invoke(messages)
        tip = response.content.strip()
        logger.info("LLM tip retrieved (%d chars)", len(tip))
        return tip

    except Exception as exc:
        logger.warning("LLM unavailable (%s) — using offline tip", exc)
        return _offline_tip(category)
