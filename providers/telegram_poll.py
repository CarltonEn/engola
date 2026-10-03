"""Long-polling for incoming Telegram messages/files, run in a background
thread. Deliberately polling (outbound GET calls from this device), never
a webhook -- a webhook needs a public HTTPS endpoint reachable by Telegram's
servers, which conflicts with Engola's whole security model (127.0.0.1
only, nothing reachable from outside the device). Polling keeps everything
outbound-only."""
import threading
import time

import requests

import config

API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
OFFSET_PATH = config.DATA_DIR / "telegram_offset.txt"
UPLOADS_DIR = config.DATA_DIR / "telegram_uploads"
POLL_TIMEOUT = 25
_stop = threading.Event()


def _load_offset() -> int:
    try:
        return int(OFFSET_PATH.read_text().strip())
    except Exception:
        return 0


def _save_offset(offset: int) -> None:
    OFFSET_PATH.write_text(str(offset))


def _download_file(file_id: str, filename: str) -> str:
    UPLOADS_DIR.mkdir(exist_ok=True)
    meta = requests.get(f"{API}/getFile", params={"file_id": file_id}, timeout=15).json()
    file_path = meta.get("result", {}).get("file_path")
    if not file_path:
        raise RuntimeError("Telegram getFile returned no file_path")
    url = f"https://api.telegram.org/file/bot{config.TELEGRAM_BOT_TOKEN}/{file_path}"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    dest = UPLOADS_DIR / filename
    dest.write_bytes(r.content)
    return str(dest)


def _extract_incoming_text(update: dict) -> str | None:
    msg = update.get("message")
    if not msg:
        return None
    chat_id = str(msg.get("chat", {}).get("id", ""))
    if config.ARCHIVE_CHAT_ID and chat_id != str(config.ARCHIVE_CHAT_ID):
        return None  # only ever respond to the owner's own chat

    text = msg.get("text", "")
    document = msg.get("document")
    if document:
        try:
            path = _download_file(document["file_id"], document.get("file_name", "telegram_file"))
            return f"[File received via Telegram, saved to {path}] {text}".strip()
        except Exception as exc:
            return f"A file was sent via Telegram but the download failed: {exc}"
    return text or None


def poll_loop(handle_incoming) -> None:
    if not (config.TELEGRAM_BOT_TOKEN and config.ARCHIVE_CHAT_ID):
        return
    offset = _load_offset()
    while not _stop.is_set():
        try:
            r = requests.get(f"{API}/getUpdates", params={"offset": offset + 1, "timeout": POLL_TIMEOUT}, timeout=POLL_TIMEOUT + 5)
            r.raise_for_status()
            for u in r.json().get("result", []):
                offset = u["update_id"]
                text = _extract_incoming_text(u)
                if text:
                    handle_incoming(text)
            _save_offset(offset)
        except Exception:
            time.sleep(3)


def start(handle_incoming) -> None:
    threading.Thread(target=poll_loop, args=(handle_incoming,), daemon=True).start()
