"""ApiLayer marketplace products. Endpoint shapes below are my best
reconstruction of ApiLayer's typical patterns, not verified against live
docs -- if any comes back 403/404, that's a wrong path guess, not
necessarily a subscription problem. Check the product's own docs tab in
your ApiLayer dashboard for the exact path if so."""
import config
import requests

BASE = "https://api.apilayer.com"


def configured() -> bool:
    return bool(config.APILAYER_KEY)


def _get(product: str, path: str, params: dict) -> dict:
    url = f"{BASE}/{product}/{path}" if path else f"{BASE}/{product}"
    r = requests.get(url, params=params, headers={"apikey": config.APILAYER_KEY}, timeout=15)
    if r.status_code in (401, 403):
        return {"error": f"{r.status_code} from '{product}' -- likely a wrong endpoint path, not a subscription issue (you're subscribed). Check the product's docs tab in your ApiLayer dashboard for the exact path."}
    if r.status_code == 404:
        return {"error": f"404 from '{product}/{path}' -- this path guess is wrong. Check the product's docs tab in your ApiLayer dashboard."}
    r.raise_for_status()
    return r.json()


def verify_email(email: str) -> dict:
    return _get("mailboxlayer", "check", {"email": email})


def flight_status(flight_number: str) -> dict:
    return _get("aviationstack", "flights", {"flight_iata": flight_number})


def country_info(name: str) -> dict:
    return _get("countrylayer", "all", {"name": name})


def ip_location(ip: str = "") -> dict:
    return _get("ipstack", ip if ip else "check", {})


def stock_quote(symbol: str) -> dict:
    return _get("marketstack", "v1/eod/latest", {"symbols": symbol.upper()})


def news_headlines(query: str = "", category: str = "") -> dict:
    params = {}
    if query:
        params["keywords"] = query
    if category:
        params["categories"] = category
    return _get("mediastack", "v1/news", params)


def geocode(address: str) -> dict:
    return _get("positionstack", "v1/forward", {"query": address})


def scrape(url: str) -> dict:
    return _get("scrapestack", "scrape", {"url": url})


def search_engine_results(query: str) -> dict:
    return _get("serpstack", "search", {"query": query})
