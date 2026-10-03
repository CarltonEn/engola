"""Mistral AI -- OpenAI-compatible endpoint. Check https://docs.mistral.ai/getting-started/models/
for current model names if the default below is retired."""
import config
from providers import openai_compat

BASE_URL = "https://api.mistral.ai/v1"


def configured() -> bool:
    return bool(config.MISTRAL_API_KEY)


def respond(history, user_text, extra_context="", allow_search_request=False) -> str:
    return openai_compat.respond(
        BASE_URL, config.MISTRAL_API_KEY, config.MISTRAL_MODEL, config.SYSTEM_PROMPT,
        history, user_text, extra_context, allow_search_request,
    )


def wants_search(reply: str):
    return openai_compat.wants_search(reply)
