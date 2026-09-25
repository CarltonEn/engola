"""Claude, via Anthropic's own Messages API (different shape from the
OpenAI-style providers: system is a top-level field, auth is x-api-key +
an anthropic-version header, not Bearer). Not one of the keys you have
ready yet -- add ANTHROPIC_API_KEY to .env (console.anthropic.com).
ANTHROPIC_MODEL defaults to a guess; check docs.anthropic.com for the
current model slug and update .env if it 404s -- these change over time."""
import requests

import config

BASE = "https://api.anthropic.com/v1"
SEARCH_TAG = "SEARCH:"


def configured() -> bool:
    return bool(config.ANTHROPIC_API_KEY)


def respond(history: list[dict], user_text: str, extra_context: str = "", allow_search_request: bool = False) -> str:
    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("Claude is not configured (ANTHROPIC_API_KEY unset)")

    system = config.SYSTEM_PROMPT
    if allow_search_request:
        system += (
            f"\nIf, and only if, answering well truly requires current/live information you "
            f"don't have, reply with EXACTLY one line: '{SEARCH_TAG} <best web search query>' "
            f"and nothing else. Otherwise just answer normally."
        )

    messages = [{"role": ("assistant" if t["role"] == "assistant" else "user"), "content": t["content"]} for t in history]
    text = user_text if not extra_context else f"{extra_context}\n\n---\n\n{user_text}"
    messages.append({"role": "user", "content": text})

    r = requests.post(
        f"{BASE}/messages",
        json={"model": config.ANTHROPIC_MODEL, "system": system, "messages": messages, "max_tokens": 1500},
        headers={
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        timeout=45,
    )
    if r.status_code == 404:
        raise RuntimeError(f"Model '{config.ANTHROPIC_MODEL}' not found -- check docs.anthropic.com for the current slug.")
    r.raise_for_status()
    blocks = r.json().get("content", [])
    answer = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    if not answer:
        raise RuntimeError("Claude returned an empty answer")
    return answer


def wants_search(reply: str) -> str | None:
    stripped = reply.strip()
    if stripped.startswith(SEARCH_TAG):
        return stripped[len(SEARCH_TAG):].strip().strip('"')
    return None
