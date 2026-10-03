#!/usr/bin/env python3
"""Engola v2 -- a local web app. Runs as one Python process in Termux and
binds to 127.0.0.1 only: you open it in the phone's own browser, nothing
outside the device can reach it. No server to host, no domain.

Telegram is two-way (archive + long-polling inbound), always outbound-only
from this device -- never a webhook, which would need public exposure.

SECURITY NOTE: this process can run arbitrary shell commands and send
email as you, and (for Gemini) the chat model itself can call those same
tools for real. HOST must stay 127.0.0.1 unless you add real auth.
"""
import re

from flask import Flask, jsonify, redirect, request, send_file, send_from_directory

import config
from device import screen, shell, termux_api
from integrations import gmail, google_oauth, ingest, worldtools
from memory import archive, history, knowledge, recall
from providers import brave, duckduckgo, elevenlabs, registry, telegram_poll, tmdb, wikipedia

app = Flask(__name__, static_folder="static", static_url_path="")
history.load()

_FAKE_NOTICE_RE = re.compile(r"(?im)^.*SYSTEM NOTICE.*$\n?")
_SHELL_CMD_LINE_RE = re.compile(
    r"(?im)^\s*(mkdir|rm|rmdir|touch|cat|grep|sed|awk|diff|pdftotext|curl|wget|"
    r"python3?|bash|sh|cd|echo|ls|cp|mv|chmod|chown|tar|unzip|pip|pkg|adb|termux-\S+)"
    r"\b.*[/~].*$"
)


def _defang_narrated_shell(reply: str) -> str:
    if not _SHELL_CMD_LINE_RE.search(reply):
        return reply
    matched = "\n".join(line.strip() for line in reply.splitlines() if _SHELL_CMD_LINE_RE.match(line))
    return (
        "I can't execute commands myself -- there's no shell access wired into this "
        "chat. Here's what I'd suggest running yourself, in the Command tab's Shell box:\n\n"
        f"```\n{matched}\n```\n\nPaste me the output afterward if you want help interpreting it."
    )


@app.before_request
def _check_access_token():
    if not config.ACCESS_TOKEN:
        return None
    supplied = request.args.get("token") or request.cookies.get("engola_token") or request.headers.get("X-Engola-Token")
    if supplied != config.ACCESS_TOKEN:
        return jsonify({"error": "missing or bad token"}), 401
    return None


@app.after_request
def _persist_token_cookie(resp):
    token = request.args.get("token")
    if config.ACCESS_TOKEN and token == config.ACCESS_TOKEN:
        resp.set_cookie("engola_token", token, httponly=True, samesite="Lax")
    return resp


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/engines")
def api_engines():
    return jsonify({"engines": registry.available(), "default": registry.default_engine()})


@app.route("/api/status")
def api_status():
    return jsonify({
        "brave_search": brave.configured(),
        "elevenlabs": elevenlabs.configured(),
        "telegram_archive": archive.telegram.configured(),
        "gmail": {"configured": google_oauth.configured(), "linked": google_oauth.linked()},
        "owner_name": config.OWNER_NAME,
    })


def process_message(text: str, engine: str | None = None):
    """Returns (engine_used, reply, embed, tool_calls). tool_calls is a
    unified list of real activity for this turn: actual Gemini tool calls,
    plus synthesized entries for search and URL ingestion, so the frontend
    can render honest 'what Engola actually did' activity cards."""
    from memory import rules as rules_mod
    cmd_reply = rules_mod.handle_command(text)
    if cmd_reply is not None:
        history.add("user", text)
        history.add("assistant", cmd_reply)
        return "system", cmd_reply, None, []

    engine = engine or registry.default_engine()
    hist = history.get()
    mem_context = knowledge.context_for(text)
    tool_calls: list[dict] = []

    ingest_block = ""
    real_notice = None
    embed = None
    url = ingest.find_url(text)
    if url:
        try:
            embed = ingest.embed_for(url)
        except Exception:
            embed = None
        try:
            result = ingest.fetch(url)
            ingest_block = (
                "SYSTEM NOTICE -- fetch succeeded. The verified content below is real; "
                "base your answer only on it, do not add facts beyond it.\n\n"
                + ingest.as_context_block(result)
            )
            if result["kind"] == "youtube_playlist":
                for v in result["videos"]:
                    for i, chunk in enumerate(ingest.chunk_text(v["text"])):
                        knowledge.add(f"[{v['title']}] (part {i + 1}) {chunk}", source=f"youtube:{v['url']}")
                archive.log_ingest(result)
                ok, fail = len(result["videos"]), len(result["errors"])
                real_notice = f"✅ Playlist ingested: {ok} video(s) transcribed and stored" + (f", {fail} failed" if fail else "")
                tool_calls.append({"name": "ingest_url", "args": {"url": url}, "result": {"kind": "youtube_playlist", "videos": ok, "failed": fail}})
            else:
                knowledge.remember(f"Ingested {result['kind']} '{result['title']}' ({result['url']}): {result['text'][:800]}")
                archive.log_ingest(result)
                real_notice = f"✅ Fetched and archived: {url}"
                tool_calls.append({"name": "ingest_url", "args": {"url": url}, "result": {"kind": result["kind"], "title": result["title"]}})
        except Exception as exc:
            ingest_block = (
                f"SYSTEM NOTICE -- fetch FAILED for {url}. Error: {exc}. "
                f"You have NO knowledge of this content -- not its title, not its topic, "
                f"nothing. Do NOT guess based on similar past links or conversation history. "
                f"Tell the user plainly that you could not fetch/read it and why"
                + (", but note the video is embedded below for them to watch directly." if embed else ".")
            )
            real_notice = f"❌ Fetch failed for {url}: {exc}"
            tool_calls.append({"name": "ingest_url", "args": {"url": url}, "result": {"error": str(exc)}})

    world_block = worldtools.try_match(text)
    recall_block = recall.as_context_block(text)
    combined_context = "\n\n".join(b for b in [mem_context, ingest_block, world_block, recall_block] if b)
    MAX_CONTEXT_CHARS = 6000
    if len(combined_context) > MAX_CONTEXT_CHARS:
        combined_context = combined_context[:MAX_CONTEXT_CHARS] + "\n\n[context truncated -- too large for some providers]"

    engine_used, reply, calls = registry.respond(engine, hist, text, extra_context=combined_context, allow_search_request=brave.configured())
    tool_calls.extend(calls)

    query = registry.wants_search(engine_used, reply)
    if query:
        blocks = []
        for fn in (
            lambda: brave.as_context_block(brave.search(query, count=5)),
            lambda: wikipedia.as_context_block(wikipedia.search(query, count=3)),
            lambda: duckduckgo.as_context_block(duckduckgo.search(query)),
            lambda: tmdb.as_context_block(tmdb.search(query)),
        ):
            try:
                blocks.append(fn())
            except Exception:
                pass
        search_block = "\n\n".join(b for b in blocks if b)
        combined = f"{combined_context}\n\n{search_block}" if (combined_context and search_block) else (search_block or combined_context)
        engine_used, reply, calls2 = registry.respond(engine_used, hist, text, extra_context=combined)
        tool_calls.extend(calls2)
        tool_calls.append({"name": "web_search", "args": {"query": query}, "result": {"found": bool(search_block)}})

    reply = _FAKE_NOTICE_RE.sub("", reply).strip()
    if not registry.has_tools(engine_used):
        reply = _defang_narrated_shell(reply)
    reply = re.sub(r"(?:\n\n---\n[✅❌].*)+$", "", reply, flags=re.S).rstrip()
    if real_notice:
        reply = f"{reply}\n\n---\n{real_notice}"

    history.add("user", text)
    history.add("assistant", reply)
    knowledge.log_turn(text, reply)
    archive.log_turn(text, reply, engine=engine_used)
    return engine_used, reply, embed, tool_calls


@app.route("/api/chat", methods=["POST"])
def api_chat():
    body = request.get_json(force=True) or {}
    text = (body.get("message") or "").strip()
    engine = body.get("engine") or registry.default_engine()
    if not text:
        return jsonify({"error": "empty message"}), 400
    try:
        engine_used, reply, embed, tool_calls = process_message(text, engine)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"reply": reply, "engine": engine_used, "embed": embed, "tool_calls": tool_calls})


def _handle_telegram_incoming(text: str) -> str:
    try:
        _, reply, _, _ = process_message(text)
        return reply
    except Exception as exc:
        return f"Error handling that message: {exc}"


@app.route("/api/history", methods=["DELETE"])
def api_history_clear():
    history.clear()
    return jsonify({"ok": True})


@app.route("/api/search")
def api_search():
    q = request.args.get("q", "")
    try:
        return jsonify({"results": brave.search(q, count=8)})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/speak", methods=["POST"])
def api_speak():
    body = request.get_json(force=True) or {}
    text = (body.get("text") or "").strip()
    try:
        audio = elevenlabs.synthesize(text)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    path = config.DATA_DIR / "speak.mp3"
    path.write_bytes(audio)
    return send_file(path, mimetype="audio/mpeg")


@app.route("/api/knowledge", methods=["GET"])
def api_knowledge_list():
    return jsonify({"notes": knowledge.all_notes()})


@app.route("/api/knowledge", methods=["POST"])
def api_knowledge_add():
    body = request.get_json(force=True) or {}
    fact = (body.get("text") or "").strip()
    if not fact:
        return jsonify({"error": "empty text"}), 400
    note_id = knowledge.remember(fact)
    archive.log_event(f"remembered: {fact}")
    return jsonify({"id": note_id})


@app.route("/api/knowledge/<int:note_id>", methods=["DELETE"])
def api_knowledge_delete(note_id):
    knowledge.delete(note_id)
    return jsonify({"ok": True})


@app.route("/api/device/shell", methods=["POST"])
def api_device_shell():
    body = request.get_json(force=True) or {}
    command = (body.get("command") or "").strip()
    force = bool(body.get("force"))
    if not command:
        return jsonify({"error": "empty command"}), 400
    if shell.is_dangerous(command) and not force:
        return jsonify({"error": "dangerous command", "requires_force": True}), 409
    result = shell.run(command)
    archive.log_event(f"shell: `{command}` -> exit {result['exit_code']}")
    return jsonify(result)


@app.route("/api/device/action", methods=["POST"])
def api_device_action():
    body = request.get_json(force=True) or {}
    action = (body.get("action") or "").strip()
    args = body.get("args") or {}
    try:
        if action == "clipboard_set":
            out = termux_api.clipboard_set(args.get("text", ""))
        elif action == "notify":
            out = termux_api.notify(args.get("title", "Engola"), args.get("body", ""))
        elif action == "sms_send":
            out = termux_api.sms_send(args.get("number", ""), args.get("text", ""))
        elif action == "photo":
            out = termux_api.camera_photo(str(config.DATA_DIR / "photo.jpg"))
        else:
            out = termux_api.run_action(action)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"result": out})


@app.route("/api/device/screen", methods=["GET"])
def api_device_screen():
    try:
        description = screen.read_screen()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"description": description})


@app.route("/api/device/screen/image", methods=["GET"])
def api_device_screen_image():
    try:
        screen.screenshot()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    return send_file(screen.SCREENSHOT_PATH, mimetype="image/png")


@app.route("/api/device/input", methods=["POST"])
def api_device_input():
    body = request.get_json(force=True) or {}
    kind = body.get("type")
    try:
        if kind == "tap":
            out = screen.tap(int(body["x"]), int(body["y"]))
        elif kind == "swipe":
            out = screen.swipe(int(body["x1"]), int(body["y1"]), int(body["x2"]), int(body["y2"]))
        elif kind == "text":
            out = screen.type_text(body.get("text", ""))
        elif kind == "key":
            out = screen.tap_key(body.get("keyevent", "KEYCODE_BACK"))
        else:
            return jsonify({"error": f"unknown input type '{kind}'"}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"result": out})


@app.route("/oauth/google/start")
def oauth_google_start():
    return redirect(google_oauth.authorization_url())


@app.route("/oauth/google/callback")
def oauth_google_callback():
    code = request.args.get("code")
    if not code:
        return "Missing ?code -- Google didn't grant authorization.", 400
    google_oauth.exchange_code(code)
    return redirect("/?gmail_linked=1")


@app.route("/api/email/status")
def api_email_status():
    return jsonify({"linked": google_oauth.linked(), "configured": google_oauth.configured()})


@app.route("/api/email/list")
def api_email_list():
    try:
        return jsonify({"messages": gmail.list_recent(request.args.get("q", ""), int(request.args.get("max", 10)))})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/email/<message_id>")
def api_email_read(message_id):
    try:
        return jsonify(gmail.read(message_id))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/email/send", methods=["POST"])
def api_email_send():
    body = request.get_json(force=True) or {}
    try:
        result = gmail.send(body.get("to", ""), body.get("subject", ""), body.get("body", ""))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502
    archive.log_event(f"email sent to {body.get('to')}: {body.get('subject')}")
    return jsonify(result)


if __name__ == "__main__":
    telegram_poll.start(_handle_telegram_incoming)
    print(f"Engola running for {config.OWNER_NAME} at http://{config.HOST}:{config.PORT}  (Ctrl+C to stop)")
    if config.HOST not in ("127.0.0.1", "localhost"):
        print("WARNING: ENGOLA_HOST is not 127.0.0.1 -- this exposes shell/email/device control to your network.")
    app.run(host=config.HOST, port=config.PORT, debug=False)
