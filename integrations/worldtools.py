"""Zero-API-key tools: weather, currency conversion, country facts.
No signup, no card, nothing to configure. Real data only -- fed to the
chat model as a verified notice, same honesty pattern as ingest.py, so
answers about weather/currency/country facts are grounded in a real fetch
instead of the model guessing or inventing numbers."""
import re

import requests

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
FX_URL = "https://api.frankfurter.dev/v1/latest"
COUNTRY_URL = "https://restcountries.com/v3.1/name/"

WEATHER_RE = re.compile(r"(?i)\bweather\b.*?\b(?:in|for|at)\s+([A-Za-z][A-Za-z\s,]{1,40})")
FX_RE = re.compile(r"(?i)\b([A-Za-z]{3})\s+(?:to|into)\s+([A-Za-z]{3})\b")
COUNTRY_RE = re.compile(r"(?i)\b(?:capital of|population of|country info(?: on| about)?)\s+([A-Za-z][A-Za-z\s]{1,40})")


def get_weather(location: str) -> str:
    g = requests.get(GEOCODE_URL, params={"name": location.strip(), "count": 1}, timeout=15)
    g.raise_for_status()
    results = g.json().get("results")
    if not results:
        raise RuntimeError(f"Couldn't find a location matching '{location}'")
    loc = results[0]
    w = requests.get(WEATHER_URL, params={
        "latitude": loc["latitude"], "longitude": loc["longitude"],
        "current": "temperature_2m,weather_code,wind_speed_10m",
    }, timeout=15)
    w.raise_for_status()
    cur = w.json().get("current", {})
    return (f"Live weather in {loc['name']}, {loc.get('country', '')}: "
            f"{cur.get('temperature_2m')}°C, wind {cur.get('wind_speed_10m')} km/h "
            f"(source: Open-Meteo, fetched just now)")


def get_exchange_rate(base: str, target: str) -> str:
    r = requests.get(FX_URL, params={"base": base.upper(), "symbols": target.upper()}, timeout=15)
    r.raise_for_status()
    rate = r.json().get("rates", {}).get(target.upper())
    if rate is None:
        raise RuntimeError(f"No live rate found for {base} -> {target}")
    return f"Live rate: 1 {base.upper()} = {rate} {target.upper()} (source: Frankfurter/ECB, fetched just now)"


def get_country_info(name: str) -> str:
    r = requests.get(COUNTRY_URL + name.strip(), timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data or not isinstance(data, list):
        raise RuntimeError(f"No country found matching '{name}'")
    c = data[0]
    capital = ", ".join(c.get("capital", ["N/A"]))
    pop = c.get("population", "N/A")
    currencies = ", ".join(c.get("currencies", {}).keys()) or "N/A"
    return (f"{c['name']['common']}: capital {capital}, population {pop:,}, "
            f"currency {currencies} (source: REST Countries, fetched just now)")


def try_match(text: str) -> str | None:
    """Best-effort: if the message looks like a weather/currency/country
    question, fetch real data and return a verified notice. Returns None
    (silently) if nothing matches or the fetch fails -- normal chat/search
    handles it instead, so this is a bonus precision layer, not a gate."""
    m = WEATHER_RE.search(text)
    if m:
        try:
            return "SYSTEM NOTICE -- verified live data below, use it exactly:\n" + get_weather(m.group(1))
        except Exception:
            return None

    m = FX_RE.search(text)
    if m:
        try:
            return "SYSTEM NOTICE -- verified live data below, use it exactly:\n" + get_exchange_rate(m.group(1), m.group(2))
        except Exception:
            return None

    m = COUNTRY_RE.search(text)
    if m:
        try:
            return "SYSTEM NOTICE -- verified live data below, use it exactly:\n" + get_country_info(m.group(1))
        except Exception:
            return None

    return None
