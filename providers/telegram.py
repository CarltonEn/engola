"""Send-only Telegram client. In v1 Telegram was the whole UI; in v2 the
web page is the UI and this is purely an archive/notification channel --
so no long-polling, no getUpdates, just sendMessage/sendDocument."""
import io

import requests

import config

API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"


def configured() -> bool:
    return bool(config.TELEGRAM_BOT_TOKEN and config.ARCHIVE_CHAT_ID)


def send_message(text: str) -> None:
    if not configured():
        return
    for i in range(0, len(text), 4000):
        try:
            requests.post(f"{API}/sendMessage", json={
                "chat_id": config.ARCHIVE_CHAT_ID, "text": text[i:i + 4000], "parse_mode": "Markdown",
            }, timeout=15)
        except Exception:
            pass


def send_document_path(path: str, caption: str = "") -> None:
    if not configured():
        return
    try:
        with open(path, "rb") as fh:
            requests.post(
                f"{API}/sendDocument",
                data={"chat_id": config.ARCHIVE_CHAT_ID, "caption": caption[:1024]},
                files={"document": (path.split("/")[-1], fh)},
                timeout=30,
            )
    except Exception:
        pass
