"""Wikipedia search -- no API key needed, uses the public REST API.
Mirrors brave.py's shape (search + as_context_block) so server.py can
treat both sources the same way."""
import requests

SEARCH_URL = "https://en.wikipedia.org/w/api.php"
SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"


def configured() -> bool:
    return True  # no key required


def search(query: str, count: int = 3) -> list[dict]:
    r = requests.get(SEARCH_URL, params={
        "action": "query", "list": "search", "srsearch": query,
        "format": "json", "srlimit": count,
    }, timeout=15)
    r.raise_for_status()
    hits = r.json().get("query", {}).get("search", [])

    results = []
    for h in hits:
        title = h["title"]
        try:
            s = requests.get(SUMMARY_URL + title.replace(" ", "_"), timeout=15)
            extract = s.json().get("extract", "") if s.ok else ""
        except Exception:
            extract = ""
        results.append({
            "title": title,
            "extract": extract,
            "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
        })
    return results


def as_context_block(results: list[dict]) -> str:
    if not results:
        return ""
    lines = ["Wikipedia results:"]
    for r in results:
        lines.append(f"- {r['title']} ({r['url']}): {r['extract'][:500]}")
    return "\n".join(lines)
