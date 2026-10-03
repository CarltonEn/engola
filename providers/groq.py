"""Groq -- OpenAI-compatible endpoint, LPU hardware, very fast inference.
Reuses openai_compat's HTTP plumbing, same pattern as grok.py/openai_api.py."""
import config
from providers import openai_compat

BASE_URL = "https://api.groq.com/openai/v1"


def configured() -> bool:
    return bool(config.GROQ_API_KEY)


def respond(history, user_text, extra_context="", allow_search_request=False) -> str:
    return openai_compat.respond(
        BASE_URL, config.GROQ_API_KEY, config.GROQ_MODEL, config.SYSTEM_PROMPT,
        history, user_text, extra_context, allow_search_request,
    )


def wants_search(reply: str):
    return openai_compat.wants_search(reply)
