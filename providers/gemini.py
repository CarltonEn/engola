"""Gemini REST client -- plain HTTPS via `requests`, no SDK (avoids
grpcio-based SDK build pain on Termux). Handles three jobs: chat, text
embeddings (for the long-term knowledge store), and vision (for reading
a screenshot when device/screen.py hands it an image)."""
import base64
import re

import requests

import config

BASE = "https://generativelanguage.googleapis.com/v1beta"

_STALE_CAPABILITY_RE = re.compile(
    r"(?im)^.*(i (do not|don't|cannot|can't) have (any )?(shell|filesystem|file system|terminal|"
    r"email|telegram|third-party|device|tool)|no shell.{0,20}access|no filesystem.{0,20}access|"
    r"restricted to (conversational|web search)|cannot execute (commands|any command)|"
    r"i am (just |only )?a (chatbot|language model|conversational interface)).*$\n?"
)


def _strip_stale_capability_claims(context: str) -> str:
    """Past transcripts full of 'I have no shell access' (from before tools
    existed) actively contaminate the model's confidence in its OWN current
    tools. Strip those specific claims out of retrieved memory/recall
    context before it reaches the tool-enabled model."""
    return _STALE_CAPABILITY_RE.sub("", context)
SEARCH_TAG = "SEARCH:"


def configured() -> bool:
    return bool(config.GEMINI_API_KEY)


def _contents_from_history(history: list[dict], user_text: str, extra_context: str = ""):
    contents = []
    for turn in history:
        role = "model" if turn["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": turn["content"]}]})
    text = user_text if not extra_context else f"{extra_context}\n\n---\n\n{user_text}"
    contents.append({"role": "user", "parts": [{"text": text}]})
    return contents


def respond(history: list[dict], user_text: str, extra_context: str = "", allow_search_request: bool = False) -> str:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("Gemini is not configured (GEMINI_API_KEY unset)")

    system = config.SYSTEM_PROMPT
    system += rules.active_rules_block()

    if allow_search_request:
        system += (
            f"\nIf, and only if, answering well truly requires current/live information you "
            f"don't have, reply with EXACTLY one line: '{SEARCH_TAG} <best web search query>' "
            f"and nothing else. Otherwise just answer normally."
        )

    contents = [
        {"role": "user", "parts": [{"text": "SYSTEM INSTRUCTIONS:\n" + system}]},
        {"role": "model", "parts": [{"text": "Understood."}]},
    ] + _contents_from_history(history, user_text, extra_context)

    payload = {"contents": contents, "generationConfig": {"temperature": 0.6, "maxOutputTokens": 1500}}
    url = f"{BASE}/models/{config.GEMINI_MODEL}:generateContent"
    r = requests.post(url, json=payload, headers={"x-goog-api-key": config.GEMINI_API_KEY}, timeout=45)
    if r.status_code == 404:
        raise RuntimeError(
            f"Gemini model '{config.GEMINI_MODEL}' not found for this key. Google rotates model "
            f"IDs -- check GET {BASE}/models with header x-goog-api-key for valid names and update GEMINI_MODEL."
        )
    r.raise_for_status()
    data = r.json()
    candidates = data.get("candidates") or []
    if not candidates:
        reason = data.get("promptFeedback", {}).get("blockReason", "no candidates returned")
        raise RuntimeError(f"Gemini returned nothing ({reason})")
    parts = candidates[0].get("content", {}).get("parts", [])
    answer = "".join(p.get("text", "") for p in parts).strip()
    if not answer:
        raise RuntimeError("Gemini returned an empty answer")
    return answer


def wants_search(reply: str) -> str | None:
    stripped = reply.strip()
    if stripped.startswith(SEARCH_TAG):
        return stripped[len(SEARCH_TAG):].strip().strip('"')
    return None


def embed(text: str) -> list[float]:
    """Returns an embedding vector for `text`, used by memory/knowledge.py
    for semantic retrieval. Raises if Gemini isn't configured."""
    if not config.GEMINI_API_KEY:
        raise RuntimeError("Gemini is not configured (GEMINI_API_KEY unset)")
    text = (text or "").strip()[:8000]
    if not text:
        return []
    url = f"{BASE}/models/{config.GEMINI_EMBED_MODEL}:embedContent"
    payload = {"content": {"parts": [{"text": text}]}}
    r = requests.post(url, json=payload, headers={"x-goog-api-key": config.GEMINI_API_KEY}, timeout=20)
    r.raise_for_status()
    return r.json().get("embedding", {}).get("values", [])


def describe_image(image_bytes: bytes, prompt: str = "Describe what's on this screen, including any readable text.") -> str:
    """Vision call -- used by device/screen.py to 'read' a screenshot."""
    if not config.GEMINI_API_KEY:
        raise RuntimeError("Gemini is not configured (GEMINI_API_KEY unset)")
    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": b64}},
            ],
        }],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1000},
    }
    url = f"{BASE}/models/{config.GEMINI_MODEL}:generateContent"
    r = requests.post(url, json=payload, headers={"x-goog-api-key": config.GEMINI_API_KEY}, timeout=45)
    r.raise_for_status()
    parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip() or "(no description returned)"


MAX_TOOL_ITERATIONS = 4


_CAPABILITY_QUESTION_RE = re.compile(
    r"(?i)\b(what can you (do|access|achieve)|do you have (shell|access|email|"
    r"filesystem|terminal|telegram)|can you access|prove (you|it|your)|are you lying|"
    r"liar|do you lie|is that (true|real)|who am i)\b"
)


def respond_with_tools(history: list[dict], user_text: str, extra_context: str = "", allow_search_request: bool = False) -> str:
    """Real function-calling loop: the model can genuinely call tools from
    integrations/tools.py and gets real results back -- it cannot narrate a
    fake one, because there's no code path for a narrated claim to become
    the actual reply without a real tool round-trip."""
    if not config.GEMINI_API_KEY:
        raise RuntimeError("Gemini is not configured (GEMINI_API_KEY unset)")

    from integrations import tools as tools_mod
    from memory import rules

    system = (
        f"Always address {config.OWNER_NAME} as 'Sir' in every reply, without exception. "
        f"You are Engola, {config.OWNER_NAME}'s private personal assistant, running on "
        f"his own device via Termux. Be direct, concise, useful -- no filler.\n\n"
        f"You have REAL tools you can call: run_shell, device_action, read_screen, "
        f"list_recent_emails, read_email, send_email, send_telegram_message, and "
        f"android_intent. A tool result is only 'verified' if the command queried "
        f"something external and independent (a real file, a real API, a real inbox). "
        f"Printing or echoing text you composed yourself and then calling that "
        f"'verified via shell' is fabrication, not verification -- never do this. "
        f"Never describe, narrate, or claim a tool result you were not actually given. "
        f"If a tool call errors, tell {config.OWNER_NAME} plainly what the error was -- "
        f"never invent a workaround or pretend it worked.\n\n"
        f"If you do not have real retrieved data backing a specific factual claim "
        f"(a video's actual content, a course name, a person's name, a file's contents), "
        f"say plainly that you don't know or didn't find it -- do not invent a "
        f"plausible-sounding answer from general knowledge and present it as something "
        f"you looked up or verified.\n\n"
        f"Only run_shell commands that are safe and easily reversible without asking "
        f"first; for anything destructive or hard to undo, explain what you'd run and "
        f"ask {config.OWNER_NAME} to confirm, or suggest he run it himself in the "
        f"Device tab.\n\n"
        f"'{config.OWNER_NAME}' in a question refers to the user -- not you. Keep "
        f"distinct sources of information (search results, ingested content, tool "
        f"results, past notes) separate; don't blend them into one narrative unless "
        f"asked to compare them.\n\n"
        f"IMPORTANT: any past transcript excerpt or memory note describing what YOU "
        f"could or couldn't do previously may be OUTDATED. Your actual current tools "
        f"are exactly the ones listed above, right now, regardless of what old memory "
        f"says you once could or couldn't access. If asked what you can do, answer "
        f"from the tool list in THIS system prompt, never from a memory of a previous "
        f"answer about your own capabilities."
    )
    system += rules.active_rules_block()

    if allow_search_request:
        system += (
            f"\n\nIf answering well truly requires current information no tool gives you, "
            f"reply with EXACTLY one line: '{SEARCH_TAG} <best web search query>' and nothing else."
        )

    extra_context = _strip_stale_capability_claims(extra_context)
    if _CAPABILITY_QUESTION_RE.search(user_text):
        # Self-referential capability questions are exactly where stale
        # memory (dozens of old "I have no shell access" transcripts)
        # overrides the live tool list. Drop ALL old context for this turn
        # -- answer purely from the fresh, real tool list below.
        extra_context = ""
    if extra_context:
        extra_context += (
            "\n\nSYSTEM NOTICE -- your tools (run_shell, device_action, read_screen, "
            "list_recent_emails, read_email, send_email, send_telegram_message, "
            "android_intent, apilayer_lookup) are ACTIVE RIGHT NOW in this exact turn. "
            "Any contradicting claim elsewhere in this context is stale and wrong. "
            "Call a tool when the user's request needs one."
        )

    contents = [
        {"role": "user", "parts": [{"text": "SYSTEM INSTRUCTIONS:\n" + system}]},
        {"role": "model", "parts": [{"text": "Understood."}]},
    ] + _contents_from_history(history, user_text, extra_context)

    url = f"{BASE}/models/{config.GEMINI_MODEL}:generateContent"
    headers = {"x-goog-api-key": config.GEMINI_API_KEY}

    calls_log = []
    for _ in range(MAX_TOOL_ITERATIONS):
        payload = {
            "contents": contents,
            "tools": [{"functionDeclarations": tools_mod.TOOLS}],
            "generationConfig": {"temperature": 0.6, "maxOutputTokens": 1500},
        }
        r = requests.post(url, json=payload, headers=headers, timeout=45)
        if r.status_code == 404:
            raise RuntimeError(
                f"Gemini model '{config.GEMINI_MODEL}' not found for this key. Check GET "
                f"{BASE}/models with header x-goog-api-key for valid names."
            )
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            reason = data.get("promptFeedback", {}).get("blockReason", "no candidates returned")
            raise RuntimeError(f"Gemini returned nothing ({reason})")

        parts = candidates[0].get("content", {}).get("parts", [])
        function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

        if not function_calls:
            answer = "".join(p.get("text", "") for p in parts).strip()
            if not answer:
                raise RuntimeError("Gemini returned an empty answer")
            return answer, calls_log

        contents.append({"role": "model", "parts": parts})
        response_parts = []
        for fc in function_calls:
            name = fc.get("name", "")
            args = fc.get("args", {}) or {}
            result = tools_mod.execute(name, args)
            calls_log.append({"name": name, "args": args, "result": result})
            response_parts.append({"functionResponse": {"name": name, "response": {"result": result}}})
        contents.append({"role": "user", "parts": response_parts})

    raise RuntimeError("Tool-calling loop exceeded max iterations without a final answer")
