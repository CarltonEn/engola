"""DuckDuckGo Instant Answer API -- free, no key, ever.
Honest limitation: NOT a general web search API. Only returns a result for
queries DDG has a structured "instant answer" for (definitions, known
entities, some calculations) -- most everyday queries return nothing.
Treat as a small bonus source alongside Wikipedia, not a Brave replacement."""
import requests

URL = "https://api.duckduckgo.com/"


def configured() -> bool:
    return True


def search(query: str) -> dict | None:
    r = requests.get(URL, params={
        "q": query, "format": "json", "no_html": 1, "skip_disambig": 1,
    }, timeout=15)
    r.raise_for_status()
    data = r.json()
    abstract = data.get("AbstractText", "")
    if not abstract:
        return None
    return {
        "heading": data.get("Heading", query),
        "text": abstract,
        "url": data.get("AbstractURL", ""),
    }


def as_context_block(result: dict | None) -> str:
    if not result:
        return ""
    return f"DuckDuckGo instant answer -- {result['heading']}: {result['text']} ({result['url']})"
