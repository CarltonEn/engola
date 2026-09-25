"""Runs shell commands on the device Engola itself is running on.

This is deliberately simple: the owner-ID check in bot.py is the real
access control (only Telegram messages from OWNER_TELEGRAM_ID ever reach
this module at all). The pattern check below is a second, much smaller
safety net against fat-fingering an obviously destructive one-liner --
not a sandbox, and not a substitute for keeping the bot token private.
"""
import re
import subprocess

import config

MAX_OUTPUT = 3500


def is_dangerous(command: str) -> bool:
    return any(re.search(p, command, re.IGNORECASE) for p in config.DANGEROUS_PATTERNS)


def run(command: str, timeout: int | None = None) -> dict:
    timeout = min(timeout or config.MAX_SHELL_TIMEOUT, 600)
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-MAX_OUTPUT:],
            "stderr": proc.stderr[-MAX_OUTPUT:],
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": f"Timed out after {timeout}s"}


def format_result(result: dict) -> str:
    parts = [f"exit code: {result['exit_code']}"]
    if result["stdout"]:
        parts.append(f"```\n{result['stdout']}\n```")
    if result["stderr"]:
        parts.append(f"stderr:\n```\n{result['stderr']}\n```")
    return "\n".join(parts)
