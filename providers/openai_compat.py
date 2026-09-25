"""Shared client for any OpenAI-compatible /chat/completions API.
Grok (x.ai) and OpenAI itself both speak this exact format, so one
function serves both providers instead of duplicating the HTTP plumbing."""
import requests

SEARCH_TAG = "SEARCH:"


def _messages_from_history(system: str, history: list[dict], user_text: str, extra_context: str = ""):
    messages = [{"role": "system", "content": system}]
    for turn in history:
        role = "assistant" if turn["role"] == "assistant" else "user"
        messages.append({"role": role, "content": turn["content"]})
    text = user_text if not extra_context else f"{extra_context}\n\n---\n\n{user_text}"
    messages.append({"role": "user", "content": text})
    return messages


def respond(base_url: str, api_key: str, model: str, system: str, history: list[dict],
            user_text: str, extra_context: str = "", allow_search_request: bool = False) -> str:
    if not api_key:
        raise RuntimeError("This provider has no API key configured")

    if allow_search_request:
        system = system + (
            f"\nIf, and only if, answering well truly requires current/live information you "
            f"don't have, reply with EXACTLY one line: '{SEARCH_TAG} <best web search query>' "
            f"and nothing else. Otherwise just answer normally."
        )

    payload = {
        "model": model,
        "messages": _messages_from_history(system, history, user_text, extra_context),
        "temperature": 0.6,
        "max_tokens": 1500,
    }
    r = requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=45,
    )
    if r.status_code == 404:
        raise RuntimeError(f"Model '{model}' not found at {base_url} -- check the provider's current model list.")
    r.raise_for_status()
    data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"No response from {base_url}: {data}")
    content = (choices[0].get("message") or {}).get("content", "").strip()
    if not content:
        raise RuntimeError("Provider returned an empty answer")
    return content


def wants_search(reply: str) -> str | None:
    stripped = reply.strip()
    if stripped.startswith(SEARCH_TAG):
        return stripped[len(SEARCH_TAG):].strip().strip('"')
    return None
