"""Grok, via x.ai's OpenAI-compatible API. Not one of the keys you have
ready yet -- add XAI_API_KEY to .env (console.x.ai) and it lights up with
no other code changes. Model names rotate; check console.x.ai if XAI_MODEL
in .env starts 404ing."""
import config
from providers import openai_compat


def configured() -> bool:
    return bool(config.XAI_API_KEY)


def respond(history: list[dict], user_text: str, extra_context: str = "", allow_search_request: bool = False) -> str:
    if not config.XAI_API_KEY:
        raise RuntimeError("Grok is not configured (XAI_API_KEY unset)")
    return openai_compat.respond(
        "https://api.x.ai/v1", config.XAI_API_KEY, config.XAI_MODEL,
        config.SYSTEM_PROMPT, history, user_text, extra_context, allow_search_request,
    )


wants_search = openai_compat.wants_search
