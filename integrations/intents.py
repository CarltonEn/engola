"""Android intents via `am start` -- lets Engola open native Android
features (Maps, Calendar, Phone dialer, browser) that have no termux-api
equivalent. This is Termux's shell reaching into Android's activity
manager -- no extra app needed beyond `android-tools` (pkg install
android-tools).

Honest limits, stated plainly rather than pretended around:
- This OPENS a screen for you to see and confirm -- by Android's own
  design, a third-party shell command cannot silently save a calendar
  event or send a message without you tapping to confirm inside that app.
- Reading your calendar or contacts is NOT included here: doing that
  reliably needs Android permissions (READ_CALENDAR, READ_CONTACTS) that
  Termux does not have and cannot grant itself. Nothing here reads them.
- Controlling third-party music apps (Spotify, YouTube Music) isn't
  possible this way either -- only opening them with a search query is.
- Android 10+ restricts starting activities from a background process.
  This usually still works because you're actively using the app when
  you trigger it, but if it silently fails, that's Android's own
  background-activity-start restriction, not a bug here.
"""
import subprocess

TIMEOUT = 15


def _am(args: list[str]) -> str:
    try:
        proc = subprocess.run(["am", *args], capture_output=True, text=True, timeout=TIMEOUT)
    except FileNotFoundError:
        return "The 'am' command isn't available -- install with: pkg install android-tools"
    except subprocess.TimeoutExpired:
        return f"Intent timed out after {TIMEOUT}s"
    out = (proc.stdout or proc.stderr or "").strip()
    return out or "Intent sent -- check your screen."


def run(args: dict) -> dict:
    kind = args.get("kind", "")

    if kind == "maps":
        query = args.get("query", "")
        if not query:
            return {"error": "maps needs a 'query'"}
        out = _am(["start", "-a", "android.intent.action.VIEW", "-d", f"geo:0,0?q={query}"])
        return {"result": out, "opened": "Google Maps", "query": query}

    if kind == "calendar_event":
        title = args.get("title", "")
        if not title:
            return {"error": "calendar_event needs a 'title'"}
        cmd = ["start", "-a", "android.intent.action.INSERT",
               "-d", "content://com.android.calendar/events",
               "--es", "title", title]
        when = args.get("when", "")
        if when:
            cmd += ["--es", "eventLocation", when]
        out = _am(cmd)
        return {"result": out, "opened": "Calendar (add-event screen, needs your confirmation)", "title": title}

    if kind == "dial":
        number = args.get("number", "")
        if not number:
            return {"error": "dial needs a 'number'"}
        out = _am(["start", "-a", "android.intent.action.DIAL", "-d", f"tel:{number}"])
        return {"result": out, "opened": "Phone dialer (call still needs your tap)", "number": number}

    if kind == "open_url":
        url = args.get("url", "")
        if not url:
            return {"error": "open_url needs a 'url'"}
        out = _am(["start", "-a", "android.intent.action.VIEW", "-d", url])
        return {"result": out, "opened": url}

    return {"error": f"Unknown intent kind '{kind}'. Valid: maps, calendar_event, dial, open_url"}
