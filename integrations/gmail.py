"""Read and send Gmail. Everything here operates as the linked Google
account -- there's no separate access control on top of the OAuth token,
so treat /oauth/google/start (and the stored token file) the same way you
treat the shell: this is real access to send mail as you."""
import base64
from email.mime.text import MIMEText

import requests

from integrations import google_oauth

BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def _headers() -> dict:
    return {"Authorization": f"Bearer {google_oauth.get_access_token()}"}


def _header_value(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def list_recent(query: str = "", max_results: int = 10) -> list[dict]:
    params = {"maxResults": max_results}
    if query:
        params["q"] = query
    r = requests.get(f"{BASE}/messages", params=params, headers=_headers(), timeout=20)
    r.raise_for_status()
    ids = [m["id"] for m in r.json().get("messages", [])]

    out = []
    for msg_id in ids:
        mr = requests.get(
            f"{BASE}/messages/{msg_id}",
            params={"format": "metadata", "metadataHeaders": ["Subject", "From", "Date"]},
            headers=_headers(), timeout=20,
        )
        mr.raise_for_status()
        data = mr.json()
        headers = data.get("payload", {}).get("headers", [])
        out.append({
            "id": msg_id,
            "from": _header_value(headers, "From"),
            "subject": _header_value(headers, "Subject"),
            "date": _header_value(headers, "Date"),
            "snippet": data.get("snippet", ""),
        })
    return out


def _extract_body(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"] + "==").decode("utf-8", errors="replace")
    for part in payload.get("parts", []) or []:
        text = _extract_body(part)
        if text:
            return text
    return ""


def read(message_id: str) -> dict:
    r = requests.get(f"{BASE}/messages/{message_id}", params={"format": "full"}, headers=_headers(), timeout=20)
    r.raise_for_status()
    data = r.json()
    headers = data.get("payload", {}).get("headers", [])
    body = _extract_body(data.get("payload", {})) or data.get("snippet", "")
    return {
        "id": message_id,
        "from": _header_value(headers, "From"),
        "to": _header_value(headers, "To"),
        "subject": _header_value(headers, "Subject"),
        "date": _header_value(headers, "Date"),
        "body": body[:5000],
    }


def send(to: str, subject: str, body: str) -> dict:
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
    r = requests.post(f"{BASE}/messages/send", json={"raw": raw}, headers=_headers(), timeout=20)
    r.raise_for_status()
    return r.json()
