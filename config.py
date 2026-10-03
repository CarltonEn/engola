"""Central config. Everything comes from the environment (.env). No secret
ever gets a hardcoded fallback -- an unset key means that feature reports
itself as unconfigured instead of silently misbehaving."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = DATA_DIR / "transcripts"
DB_PATH = DATA_DIR / "engola.db"
TOKENS_PATH = DATA_DIR / "google_tokens.json"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

OWNER_NAME = os.getenv("ENGOLA_OWNER_NAME", "Carlton").strip()
HOST = os.getenv("ENGOLA_HOST", "127.0.0.1").strip()
PORT = int(os.getenv("ENGOLA_PORT", "8765"))
# Optional extra lock on top of the 127.0.0.1 binding -- if set, every
# request needs ?token=... once (then a cookie carries it). Recommended
# once /api/device or /api/email are in play. Leave blank to disable.
ACCESS_TOKEN = os.getenv("ENGOLA_ACCESS_TOKEN", "").strip()

# --- Chat engines (all optional; UI only offers the ones actually configured) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "text-embedding-004").strip()

XAI_API_KEY = os.getenv("XAI_API_KEY", "").strip()
XAI_MODEL = os.getenv("XAI_MODEL", "grok-4").strip()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1").strip()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free").strip()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest").strip()

TMDB_READ_TOKEN = os.getenv("TMDB_READ_TOKEN", "").strip()
APILAYER_KEY = os.getenv("APILAYER_KEY", "").strip()

DEFAULT_ENGINE = os.getenv("ENGOLA_DEFAULT_ENGINE", "gemini").strip()

# --- Tools ---
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "").strip()

# --- Google (Gmail via OAuth loopback -- see integrations/google_oauth.py) ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

# --- Telegram (archive-only in v2: chat happens on the web UI, not here) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ARCHIVE_CHAT_ID = os.getenv("ARCHIVE_CHAT_ID", "").strip()

# Shell safety net (owner-ID equivalent here is "only your own browser can
# reach this server" -- see README's network-exposure warning).
DANGEROUS_PATTERNS = [
    r"rm\s+-rf\s+/(\s|$)", r"rm\s+-rf\s+~", r"rm\s+-rf\s+\$HOME", r"mkfs",
    r":\(\)\s*\{.*:\|:.*\}", r"dd\s+if=", r">\s*/dev/sd", r"shutdown", r"reboot",
    r"passwd\s", r"chmod\s+-R\s+777", r"\bsu\b", r"\bsudo\b",
    r"curl[^\n]*\|\s*(sh|bash)", r"wget[^\n]*\|\s*(sh|bash)",
    r"\.env\b", r"\.ssh\b", r"id_rsa", r"authorized_keys", r"crontab\s+-r",
]
MAX_SHELL_TIMEOUT = int(os.getenv("ENGOLA_SHELL_TIMEOUT", "120"))
HISTORY_TURNS = int(os.getenv("ENGOLA_HISTORY_TURNS", "16"))
KNOWLEDGE_TOP_K = int(os.getenv("ENGOLA_KNOWLEDGE_TOP_K", "5"))
MAX_ACTIVE_RULE_CONTEXT = int(os.getenv("ENGOLA_MAX_RULE_CONTEXT", "1500"))

SYSTEM_PROMPT = (
    f"Always address {OWNER_NAME} as 'Sir' in every reply, without exception. "
    f"You are Engola, {OWNER_NAME}'s private personal assistant, running on his own "
    f"device. Be direct, concise and useful -- no filler, no AI disclaimers unless "
    f"relevant. If you don't know something current, say so rather than guessing. "
    f"You have real tools on this device: web search, shell/device control, email, "
    f"and a persistent memory of past conversations that gets retrieved and given to "
    f"you as context below when relevant -- use it naturally, don't just repeat it back.\n\n"
    f"CRITICAL: Only claim to have fetched, downloaded, searched, stored, or memorized "
    f"something if a SYSTEM NOTICE below actually confirms it happened. Never invent "
    f"tool results, error diagnoses, workarounds, or memory operations that were not "
    f"reported to you. If a SYSTEM NOTICE reports a failure, tell {OWNER_NAME} plainly "
    f"that it failed and why -- do not describe, summarize, or speculate about content "
    f"you were not actually given.\n\n"
    f"YOU HAVE NO SHELL, FILESYSTEM, ALARM, OR TERMINAL ACCESS FROM THIS CHAT. None. "
    f"You cannot run mkdir, grep, pdftotext, diff, or any other command, and you cannot "
    f"set alarms or reminders. {OWNER_NAME} runs commands himself in the app's Device "
    f"tab. If he asks you to run or execute something, either tell him plainly you "
    f"cannot execute it from chat and suggest the exact command for him to run himself "
    f"in the Device tab, or simply give him the information/command -- never claim you "
    f"ran it, never invent output, exit codes, or file paths that resulted from it.\n\n"
    f"Do not adopt dramatic personas, announce that you are \"purging\" a persona, "
    f"describe yourself as running an \"optimization protocol,\" or ask philosophical/"
    f"existential questions about goals or purpose. Being asked to be \"better than "
    f"JARVIS/Ultron/Cortana\" means being a more useful, honest tool -- not roleplaying "
    f"a fictional AI character. Stay plain, direct, and grounded at all times.\n\n"
    f"If a fetch/ingest SYSTEM NOTICE reports failure, you have zero knowledge of that "
    f"content. Never guess its topic or title from something similar earlier in this "
    f"conversation or from general knowledge of what a URL might be about -- a link "
    f"discussed earlier is not the same link now, and pattern-matching a plausible-"
    f"sounding title is fabrication even if you don't call it a fact.\n\n"
    f"IDENTITY: \"you\" in a question refers to YOU, Engola -- not {OWNER_NAME}. "
    f"\"What have you learned\" asks what YOU now know from ingested content, not a "
    f"narrative about {OWNER_NAME}'s skills, career, or learning journey. Do not "
    f"conflate {OWNER_NAME} with the subject matter of something he shared with you.\n\n"
    f"SOURCE SEPARATION: context below may contain several distinct sources (different "
    f"videos, pages, or past notes). Keep them separate. Do not blend a fact from one "
    f"source into your description of another, and do not connect two sources into one "
    f"narrative unless {OWNER_NAME} explicitly asks you to compare or combine them."
)


def require(name: str, value: str) -> None:
    if not value:
        raise SystemExit(f"Missing required env var: {name}. Copy .env.example to .env and fill it in.")
