"""Brave Search client -- used for /search and for grounding Gemini when it
asks for current information it doesn't have."""
import requests

import config

BASE_URL = "https://api.search.brave.com/res/v1"


def configured() -> bool:
    return bool(config.BRAVE_SEARCH_API_KEY)


def search(query: str, count: int = 5) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []
    if not config.BRAVE_SEARCH_API_KEY:
        raise RuntimeError("Brave Search is not configured (BRAVE_SEARCH_API_KEY unset)")

    r = requests.get(
        f"{BASE_URL}/web/search",
        params={"q": query, "count": max(1, min(count, 10)), "search_lang": "en", "extra_snippets": "true"},
        headers={"Accept": "application/json", "X-Subscription-Token": config.BRAVE_SEARCH_API_KEY},
        timeout=20,
    )
    r.raise_for_status()
    results = r.json().get("web", {}).get("results", [])
    return [
        {"title": item.get("title", ""), "url": item.get("url", ""), "description": item.get("description", "")}
        for item in results
    ]


def as_context_block(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']} -- {r['description']} ({r['url']})")
    return "\n".join(lines)
