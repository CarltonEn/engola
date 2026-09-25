"""OpenAI/GPT provider. Not one of the keys you have ready yet -- add
OPENAI_API_KEY to .env (platform.openai.com) and it lights up."""
import config
from providers import openai_compat


def configured() -> bool:
    return bool(config.OPENAI_API_KEY)


def respond(history: list[dict], user_text: str, extra_context: str = "", allow_search_request: bool = False) -> str:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OpenAI is not configured (OPENAI_API_KEY unset)")
    return openai_compat.respond(
        "https://api.openai.com/v1", config.OPENAI_API_KEY, config.OPENAI_MODEL,
        config.SYSTEM_PROMPT, history, user_text, extra_context, allow_search_request,
    )


wants_search = openai_compat.wants_search
