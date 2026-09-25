"""Wraps the `termux-api` command-line tools (from the Termux:API app +
`pkg install termux-api`) so Engola can actually touch the phone: battery,
clipboard, notifications, vibration, torch, volume, location, SMS, camera.

Each function shells out to one termux-api binary and returns plain text.
If the Termux:API app/package isn't installed, every call fails with a
clear message rather than hanging.
"""
import json
import shlex
import subprocess

TIMEOUT = 20

ACTIONS = {
    "battery": "termux-battery-status",
    "clipboard_get": "termux-clipboard-get",
    "torch_on": "termux-torch on",
    "torch_off": "termux-torch off",
    "vibrate": "termux-vibrate -d 300",
    "wifi": "termux-wifi-connectioninfo",
    "location": "termux-location -p gps -r once",
    "sms_list": "termux-sms-list -l 10",
    "volume": "termux-volume",
}


def _run(cmd: str) -> str:
    try:
        proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=TIMEOUT)
    except FileNotFoundError:
        return (
            "termux-api is not installed. On the phone: install the 'Termux:API' app "
            "from F-Droid/Play Store, then run `pkg install termux-api`."
        )
    except subprocess.TimeoutExpired:
        return f"{cmd} timed out after {TIMEOUT}s (check the Termux:API app has the needed permission)."
    out = (proc.stdout or proc.stderr or "").strip()
    return out or "(no output)"


def run_action(name: str) -> str:
    if name not in ACTIONS:
        return f"Unknown device action '{name}'. Options: {', '.join(sorted(ACTIONS))}, clipboard_set, notify, share."
    return _run(ACTIONS[name])


def clipboard_set(text: str) -> str:
    try:
        subprocess.run(["termux-clipboard-set"], input=text, text=True, timeout=TIMEOUT)
        return "Copied to clipboard."
    except FileNotFoundError:
        return "termux-api is not installed (see /device help)."


def notify(title: str, content: str) -> str:
    try:
        subprocess.run(
            ["termux-notification", "--title", title, "--content", content],
            timeout=TIMEOUT,
        )
        return "Notification sent."
    except FileNotFoundError:
        return "termux-api is not installed (see /device help)."


def sms_send(number: str, text: str) -> str:
    try:
        subprocess.run(["termux-sms-send", "-n", number, text], timeout=TIMEOUT)
        return f"SMS sent to {number}."
    except FileNotFoundError:
        return "termux-api is not installed (see /device help)."


def camera_photo(path: str) -> str:
    try:
        subprocess.run(["termux-camera-photo", "-c", "0", path], timeout=TIMEOUT)
        return path
    except FileNotFoundError:
        return "termux-api is not installed (see /device help)."


HELP = (
    "Device actions: " + ", ".join(sorted(ACTIONS)) + ", clipboard_set <text>, "
    "notify <title> | <text>, sms_send <number> <text>, photo\n"
    "Requires the Termux:API app installed + `pkg install termux-api`."
)
