"""Deterministic Rule Vault -- standing behavioral rules, loaded UNCONDITIONALLY
into every prompt (subject to a size budget). Never retrieved via semantic/keyword
search like memory/knowledge.py's notes table -- rules must not compete against
ordinary memory for a context slot based on relevance (see config.MAX_ACTIVE_RULE_CONTEXT).
Command handling also means rule-management messages never reach
knowledge.log_turn(), so they never pollute the fuzzy-retrieval notes table.
"""
import sqlite3
from datetime import datetime, timezone

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    source TEXT NOT NULL DEFAULT 'user',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3}


def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def add_rule(content: str, priority: str = "normal", source: str = "user") -> int:
    content = (content or "").strip()
    if not content:
        return -1
    priority = priority if priority in _PRIORITY_ORDER else "normal"
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO rules (content, priority, source, active, created_at, updated_at) "
            "VALUES (?, ?, ?, 1, ?, ?)",
            (content, priority, source, now, now),
        )
        return cur.lastrowid


def list_rules(active_only: bool = False) -> list:
    with _conn() as conn:
        q = "SELECT id, content, priority, source, active, created_at, updated_at FROM rules"
        if active_only:
            q += " WHERE active = 1"
        q += " ORDER BY id DESC"
        rows = conn.execute(q).fetchall()
    return [
        {"id": i, "content": c, "priority": p, "source": s, "active": bool(a),
         "created_at": ca, "updated_at": ua}
        for i, c, p, s, a, ca, ua in rows
    ]


def deactivate_rule(rule_id: int) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        cur = conn.execute("UPDATE rules SET active = 0, updated_at = ? WHERE id = ?", (now, rule_id))
        return cur.rowcount > 0


def delete_rule(rule_id: int) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        return cur.rowcount > 0


def active_rules_block(max_chars: int = None) -> str:
    """Deterministic, priority-ordered, unconditionally included in the prompt --
    never competes for a context slot via semantic/keyword relevance."""
    max_chars = max_chars or config.MAX_ACTIVE_RULE_CONTEXT
    active = list_rules(active_only=True)
    active.sort(key=lambda r: (_PRIORITY_ORDER.get(r["priority"], 2), r["id"]))
    if not active:
        return ""

    header = "[ACTIVE RULES -- standing instructions, not retrieved memory, always apply]"
    lines = [header]
    used = len(header)
    for r in active:
        line = f"- ({r['priority']}) {r['content']}"
        if used + len(line) + 1 > max_chars:
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines) + "\n\n"


def handle_command(text: str):
    """Returns a reply string if `text` is a rule-vault command, else None --
    meaning it's not a command and the normal chat flow should handle it."""
    t = (text or "").strip()

    if t.startswith("/rule!"):
        content = t[len("/rule!"):].strip()
        if not content:
            return "Usage: /rule! <critical rule text>"
        rid = add_rule(content, priority="critical")
        return f"Rule #{rid} added (critical)."

    if t.startswith("/rule "):
        content = t[len("/rule "):].strip()
        if not content:
            return "Usage: /rule <rule text>"
        rid = add_rule(content, priority="normal")
        return f"Rule #{rid} added (normal)."

    if t == "/rules":
        active = list_rules(active_only=True)
        if not active:
            return "No active rules."
        active.sort(key=lambda r: (_PRIORITY_ORDER.get(r["priority"], 2), r["id"]))
        lines = [f"#{r['id']} ({r['priority']}) {r['content']}" for r in active]
        return "Active rules:\n" + "\n".join(lines)

    if t.startswith("/forget rule "):
        raw = t[len("/forget rule "):].strip()
        if not raw.isdigit():
            return "Usage: /forget rule <id>"
        ok = deactivate_rule(int(raw))
        return f"Rule #{raw} deactivated." if ok else f"No rule #{raw} found."

    return None
