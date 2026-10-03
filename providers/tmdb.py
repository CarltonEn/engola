"""TMDB -- movie/TV metadata lookups, free with a read-access token."""
import config
import requests

BASE_URL = "https://api.themoviedb.org/3"


def configured() -> bool:
    return bool(config.TMDB_READ_TOKEN)


def search(query: str) -> dict | None:
    r = requests.get(f"{BASE_URL}/search/multi", params={"query": query},
                      headers={"Authorization": f"Bearer {config.TMDB_READ_TOKEN}"}, timeout=15)
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return None
    top = results[0]
    title = top.get("title") or top.get("name", "Unknown")
    overview = top.get("overview", "")
    date = top.get("release_date") or top.get("first_air_date", "")
    return {"title": title, "date": date, "overview": overview}


def as_context_block(result: dict | None) -> str:
    if not result:
        return ""
    return f"TMDB: {result['title']} ({result['date']}) -- {result['overview']}"
