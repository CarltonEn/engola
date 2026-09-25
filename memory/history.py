"""Short-term memory: the last N turns, for immediate conversational
continuity. This is separate from memory/knowledge.py, which is the
long-term store that gets searched and injected as context."""
import json

import config

_STATE_FILE = config.DATA_DIR / "history.json"
_STATE = {"history": []}


def load() -> None:
    if _STATE_FILE.exists():
        try:
            _STATE["history"] = json.loads(_STATE_FILE.read_text()).get("history", [])
        except Exception:
            _STATE["history"] = []


def _save() -> None:
    _STATE_FILE.write_text(json.dumps({"history": _STATE["history"]}, ensure_ascii=False, indent=2))


def get() -> list[dict]:
    if not _STATE["history"]:
        load()
    return _STATE["history"]


def add(role: str, content: str) -> None:
    _STATE["history"].append({"role": role, "content": content})
    _STATE["history"][:] = _STATE["history"][-(config.HISTORY_TURNS * 2):]
    _save()


def clear() -> None:
    _STATE["history"] = []
    _save()
