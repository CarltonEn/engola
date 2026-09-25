"""Gemini REST client -- plain HTTPS via `requests`, no SDK (avoids
grpcio-based SDK build pain on Termux). Handles three jobs: chat, text
embeddings (for the long-term knowledge store), and vision (for reading
a screenshot when device/screen.py hands it an image)."""
import base64

import requests

import config

BASE = "https://generativelanguage.googleapis.com/v1beta"
SEARCH_TAG = "SEARCH:"


def configured() -> bool:
    return bool(config.GEMINI_API_KEY)


def _contents_from_history(history: list[dict], user_text: str, extra_context: str = ""):
    contents = []
    for turn in history:
        role = "model" if turn["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": turn["content"]}]})
    text = user_text if not extra_context else f"{extra_context}\n\n---\n\n{user_text}"
    contents.append({"role": "user", "parts": [{"text": text}]})
    return contents


def respond(history: list[dict], user_text: str, extra_context: str = "", allow_search_request: bool = False) -> str:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("Gemini is not configured (GEMINI_API_KEY unset)")

    system = config.SYSTEM_PROMPT
    if allow_search_request:
        system += (
            f"\nIf, and only if, answering well truly requires current/live information you "
            f"don't have, reply with EXACTLY one line: '{SEARCH_TAG} <best web search query>' "
            f"and nothing else. Otherwise just answer normally."
        )

    contents = [
        {"role": "user", "parts": [{"text": "SYSTEM INSTRUCTIONS:\n" + system}]},
        {"role": "model", "parts": [{"text": "Understood."}]},
    ] + _contents_from_history(history, user_text, extra_context)

    payload = {"contents": contents, "generationConfig": {"temperature": 0.6, "maxOutputTokens": 1500}}
    url = f"{BASE}/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    r = requests.post(url, json=payload, timeout=45)
    if r.status_code == 404:
        raise RuntimeError(
            f"Gemini model '{config.GEMINI_MODEL}' not found for this key. Google rotates model "
            f"IDs -- check GET {BASE}/models?key=... for valid names and update GEMINI_MODEL."
        )
    r.raise_for_status()
    data = r.json()
    candidates = data.get("candidates") or []
    if not candidates:
        reason = data.get("promptFeedback", {}).get("blockReason", "no candidates returned")
        raise RuntimeError(f"Gemini returned nothing ({reason})")
    parts = candidates[0].get("content", {}).get("parts", [])
    answer = "".join(p.get("text", "") for p in parts).strip()
    if not answer:
        raise RuntimeError("Gemini returned an empty answer")
    return answer


def wants_search(reply: str) -> str | None:
    stripped = reply.strip()
    if stripped.startswith(SEARCH_TAG):
        return stripped[len(SEARCH_TAG):].strip().strip('"')
    return None


def embed(text: str) -> list[float]:
    """Returns an embedding vector for `text`, used by memory/knowledge.py
    for semantic retrieval. Raises if Gemini isn't configured."""
    if not config.GEMINI_API_KEY:
        raise RuntimeError("Gemini is not configured (GEMINI_API_KEY unset)")
    text = (text or "").strip()[:8000]
    if not text:
        return []
    url = f"{BASE}/models/{config.GEMINI_EMBED_MODEL}:embedContent?key={config.GEMINI_API_KEY}"
    payload = {"content": {"parts": [{"text": text}]}}
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()
    return r.json().get("embedding", {}).get("values", [])


def describe_image(image_bytes: bytes, prompt: str = "Describe what's on this screen, including any readable text.") -> str:
    """Vision call -- used by device/screen.py to 'read' a screenshot."""
    if not config.GEMINI_API_KEY:
        raise RuntimeError("Gemini is not configured (GEMINI_API_KEY unset)")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": b64}},
            ],
        }],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1000},
    }
    url = f"{BASE}/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
    r = requests.post(url, json=payload, timeout=45)
    r.raise_for_status()
    parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip() or "(no description returned)"
