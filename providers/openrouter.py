"""OpenRouter -- OpenAI-compatible proxy aggregating many models.
Check https://openrouter.ai/models for current free-tier model IDs --
the one below may rotate; verify it still exists before relying on it."""
import config
from providers import openai_compat

BASE_URL = "https://openrouter.ai/api/v1"


def configured() -> bool:
    return bool(config.OPENROUTER_API_KEY)


def respond(history, user_text, extra_context="", allow_search_request=False) -> str:
    return openai_compat.respond(
        BASE_URL, config.OPENROUTER_API_KEY, config.OPENROUTER_MODEL, config.SYSTEM_PROMPT,
        history, user_text, extra_context, allow_search_request,
    )


def wants_search(reply: str):
    return openai_compat.wants_search(reply)
