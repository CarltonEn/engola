"""'Read the screen' is not something a plain Termux shell can do on its
own -- Android sandboxes apps from each other, and there's no termux-api
command for it. The real, legitimate, no-root path is the same one
Android's own developer tools use: pair Termux to the device's own ADB
(Android Debug Bridge) over Wireless Debugging, which Google explicitly
built for exactly this kind of on-device automation and testing.

One-time setup on the phone (not automatable -- it's a deliberate consent
step by design):
  1. `pkg install android-tools` in Termux
  2. Settings -> Developer options -> Wireless debugging -> ON
  3. "Pair device with pairing code" -> note the IP:port and 6-digit code
  4. `adb pair <ip>:<port>` in Termux, enter the code
  5. `adb connect <ip>:<port>` (the regular debugging port, shown on the
     same screen) -- after this, `adb devices` should list it as authorized

This grants real control (screenshots AND simulated taps/typing), which is
strictly more powerful than the other device/ modules -- treat pairing it
as a deliberate, bigger trust decision than installing termux-api.
"""
import shlex
import subprocess

import config

TIMEOUT = 20
SCREENSHOT_PATH = str(config.DATA_DIR / "screen.png")


def _adb(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["adb", *args], capture_output=True, timeout=TIMEOUT)


def connected() -> bool:
    try:
        out = _adb("devices").stdout.decode()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    lines = [l for l in out.splitlines()[1:] if l.strip()]
    return any(l.endswith("device") for l in lines)  # excludes 'unauthorized'/'offline'


def _require_connection():
    if not connected():
        raise RuntimeError(
            "No authorized adb device. Run `adb devices` in Termux -- if it's empty or says "
            "'unauthorized', redo the Wireless Debugging pairing (see device/screen.py docstring)."
        )


def screenshot() -> bytes:
    _require_connection()
    proc = subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=TIMEOUT)
    if not proc.stdout:
        raise RuntimeError(f"Screenshot failed: {proc.stderr.decode()[:300]}")
    with open(SCREENSHOT_PATH, "wb") as fh:
        fh.write(proc.stdout)
    return proc.stdout


def read_screen() -> str:
    """Screenshot + Gemini vision -> a text description of what's on screen,
    including any readable text. This is the actual 'reads your screen'
    feature -- OCR-via-vision-model, not a live accessibility feed."""
    image = screenshot()
    from providers import gemini
    return gemini.describe_image(image)


def tap(x: int, y: int) -> str:
    _require_connection()
    _adb("shell", "input", "tap", str(x), str(y))
    return f"Tapped ({x}, {y})"


def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> str:
    _require_connection()
    _adb("shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))
    return f"Swiped ({x1},{y1}) -> ({x2},{y2})"


def type_text(text: str) -> str:
    _require_connection()
    # adb input text needs spaces escaped
    _adb("shell", "input", "text", shlex.quote(text).replace(" ", "%s"))
    return "Typed."


def tap_key(keyevent: str) -> str:
    """E.g. 'KEYCODE_BACK', 'KEYCODE_HOME', 'KEYCODE_ENTER'."""
    _require_connection()
    _adb("shell", "input", "keyevent", keyevent)
    return f"Sent {keyevent}"
