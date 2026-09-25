"""Google OAuth for Gmail, using the 'loopback' flow (RFC 8252): the
consent screen redirects back to http://127.0.0.1:<port>/oauth/google/callback
on this same device/browser -- no public domain or tunnel needed, which is
exactly what makes this workable from a phone with no server to host on.

Create the OAuth client at console.cloud.google.com as a **Desktop app**
type (not "Web application") -- Desktop app clients don't require the
redirect URI to be pre-registered exactly, which matters since Termux's
port can vary.
"""
import json
import time
import urllib.parse

import requests

import config

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def redirect_uri() -> str:
    return f"http://127.0.0.1:{config.PORT}/oauth/google/callback"


def configured() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)


def authorization_url() -> str:
    if not configured():
        raise RuntimeError("Google OAuth is not configured (GOOGLE_CLIENT_ID/SECRET unset)")
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join(config.GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # forces a refresh_token every time, useful while testing
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code(code: str) -> dict:
    r = requests.post(TOKEN_URL, data={
        "code": code,
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri(),
        "grant_type": "authorization_code",
    }, timeout=20)
    r.raise_for_status()
    tokens = r.json()
    tokens["obtained_at"] = time.time()
    _save(tokens)
    return tokens


def _save(tokens: dict) -> None:
    config.TOKENS_PATH.write_text(json.dumps(tokens, indent=2))


def _load() -> dict | None:
    if not config.TOKENS_PATH.exists():
        return None
    try:
        return json.loads(config.TOKENS_PATH.read_text())
    except Exception:
        return None


def linked() -> bool:
    return _load() is not None


def get_access_token() -> str:
    """Returns a valid access token, refreshing it first if it's expired.
    Raises if Gmail was never linked (send them through authorization_url())."""
    tokens = _load()
    if not tokens:
        raise RuntimeError("Gmail isn't linked yet -- visit /oauth/google/start in the app first.")

    age = time.time() - tokens.get("obtained_at", 0)
    if age < tokens.get("expires_in", 3600) - 60:
        return tokens["access_token"]

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Access token expired and no refresh_token was stored -- re-link at /oauth/google/start.")

    r = requests.post(TOKEN_URL, data={
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=20)
    r.raise_for_status()
    refreshed = r.json()
    tokens["access_token"] = refreshed["access_token"]
    tokens["expires_in"] = refreshed.get("expires_in", 3600)
    tokens["obtained_at"] = time.time()
    _save(tokens)
    return tokens["access_token"]
