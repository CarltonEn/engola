"""Registry of chat engines. Adding a fifth provider later means writing
providers/whatever.py with configured()/respond()/wants_search(), then
adding one line to ENGINES and AUTO_ORDER below -- nothing else changes.

"auto" is a virtual engine id: it tries configured engines in AUTO_ORDER
and falls through to the next one if a call raises (rate limit, outage,
bad key, etc.) instead of failing the whole turn.

respond() returns (engine_used, reply_text, tool_calls) -- tool_calls is a
list of {"name","args","result"} dicts, empty for engines without real
tool access (everything except Gemini currently)."""
import config
from providers import anthropic_api, gemini, grok, groq, mistral, openai_api, openrouter, tmdb

ENGINES = {
    "gemini": {"label": "Gemini 2.0 Flash", "module": gemini},
    "grok": {"label": "Grok (x.ai)", "module": grok},
    "groq": {"label": "Groq (fast inference)", "module": groq},
    "openai": {"label": "GPT (OpenAI)", "module": openai_api},
    "claude": {"label": "Claude (Anthropic)", "module": anthropic_api},
    "openrouter": {"label": "OpenRouter", "module": openrouter},
    "mistral": {"label": "Mistral", "module": mistral},
}

AUTO_ORDER = ["gemini", "groq", "claude", "openai", "grok", "openrouter", "mistral"]


def _configured_engines() -> list[str]:
    return [k for k in AUTO_ORDER if k in ENGINES and ENGINES[k]["module"].configured()]


def available() -> list[dict]:
    items = [
        {"id": key, "label": v["label"], "configured": v["module"].configured()}
        for key, v in ENGINES.items()
    ]
    return [{"id": "auto", "label": "Auto (best available)", "configured": bool(_configured_engines())}] + items


def default_engine() -> str:
    if _configured_engines():
        return "auto"
    return config.DEFAULT_ENGINE


def has_tools(engine_id: str) -> bool:
    module = ENGINES.get(engine_id, {}).get("module")
    return bool(module and hasattr(module, "respond_with_tools"))


def _call(engine_id: str, history, user_text, extra_context, allow_search_request):
    module = ENGINES[engine_id]["module"]
    if hasattr(module, "respond_with_tools"):
        return module.respond_with_tools(history, user_text, extra_context, allow_search_request)
    return module.respond(history, user_text, extra_context, allow_search_request), []


def respond(engine_id: str, history: list[dict], user_text: str, extra_context: str = "", allow_search_request: bool = False):
    """Returns (engine_used, reply_text, tool_calls)."""
    if engine_id == "auto":
        candidates = _configured_engines()
        if not candidates:
            raise RuntimeError("No chat engine is configured. Set at least one API key in .env.")
        last_err = None
        for eid in candidates:
            try:
                text, calls = _call(eid, history, user_text, extra_context, allow_search_request)
                return eid, text, calls
            except Exception as exc:
                last_err = exc
        raise RuntimeError(f"All configured engines failed. Last error: {last_err}")

    if engine_id not in ENGINES:
        raise RuntimeError(f"Unknown engine '{engine_id}'. Options: auto, {', '.join(ENGINES)}")
    text, calls = _call(engine_id, history, user_text, extra_context, allow_search_request)
    return engine_id, text, calls


def wants_search(engine_id: str, reply: str) -> str | None:
    if engine_id not in ENGINES:
        return None
    return ENGINES[engine_id]["module"].wants_search(reply)
