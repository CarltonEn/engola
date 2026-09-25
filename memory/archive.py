"""Every exchange gets written to a local daily markdown transcript. If
Telegram archiving is configured (TELEGRAM_BOT_TOKEN + ARCHIVE_CHAT_ID),
it's also pushed there live plus as a full .md file backup periodically --
same behavior as v1, just no longer doubling as the chat UI itself."""
from datetime import datetime

import config
from providers import telegram

ARCHIVE_FILE_EVERY = 20
_counter = {"n": 0}


def _today_path():
    day = datetime.now().strftime("%Y-%m-%d")
    return config.LOG_DIR / f"{day}.md", day


def log_turn(user_text: str, assistant_text: str, engine: str = "") -> None:
    path, day = _today_path()
    ts = datetime.now().strftime("%H:%M:%S")
    tag = f" _{engine}_" if engine else ""
    entry = f"\n### {ts}{tag}\n\n**{config.OWNER_NAME}:** {user_text}\n\n**Engola:** {assistant_text}\n"
    is_new = not path.exists()
    with open(path, "a", encoding="utf-8") as fh:
        if is_new:
            fh.write(f"# Engola transcript -- {day}\n")
        fh.write(entry)

    telegram.send_message(f"🗒 *{ts}*\n*{config.OWNER_NAME}:* {user_text}\n*Engola:* {assistant_text}")

    _counter["n"] += 1
    if _counter["n"] % ARCHIVE_FILE_EVERY == 0:
        push_today_file()


def push_today_file() -> None:
    path, day = _today_path()
    if path.exists():
        telegram.send_document_path(str(path), caption=f"Transcript backup -- {day}")


def log_event(text: str) -> None:
    path, day = _today_path()
    ts = datetime.now().strftime("%H:%M:%S")
    is_new = not path.exists()
    with open(path, "a", encoding="utf-8") as fh:
        if is_new:
            fh.write(f"# Engola transcript -- {day}\n")
        fh.write(f"\n> **{ts} [event]** {text}\n")
