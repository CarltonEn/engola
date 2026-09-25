"""Registry of chat engines. Adding a fifth provider later means writing
providers/whatever.py with configured()/respond()/wants_search(), then
adding one line to ENGINES below -- nothing else in the app changes."""
import config
from providers import anthropic_api, gemini, grok, openai_api

ENGINES = {
    "gemini": {"label": "Gemini 2.0 Flash", "module": gemini},
    "grok": {"label": "Grok (x.ai)", "module": grok},
    "openai": {"label": "GPT (OpenAI)", "module": openai_api},
    "claude": {"label": "Claude (Anthropic)", "module": anthropic_api},
}


def available() -> list[dict]:
    return [
        {"id": key, "label": v["label"], "configured": v["module"].configured()}
        for key, v in ENGINES.items()
    ]


def default_engine() -> str:
    if config.DEFAULT_ENGINE in ENGINES and ENGINES[config.DEFAULT_ENGINE]["module"].configured():
        return config.DEFAULT_ENGINE
    for key, v in ENGINES.items():
        if v["module"].configured():
            return key
    return config.DEFAULT_ENGINE  # none configured -- caller will surface the resulting error


def respond(engine_id: str, history: list[dict], user_text: str, extra_context: str = "", allow_search_request: bool = False) -> str:
    if engine_id not in ENGINES:
        raise RuntimeError(f"Unknown engine '{engine_id}'. Options: {', '.join(ENGINES)}")
    return ENGINES[engine_id]["module"].respond(history, user_text, extra_context, allow_search_request)


def wants_search(engine_id: str, reply: str) -> str | None:
    return ENGINES[engine_id]["module"].wants_search(reply)
