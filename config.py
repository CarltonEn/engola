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

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1").strip()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5").strip()

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
    r"rm\s+-rf\s+/(\s|$)", r"mkfs", r":\(\)\s*\{.*:\|:.*\}", r"dd\s+if=",
    r">\s*/dev/sd", r"shutdown", r"reboot", r"passwd\s", r"chmod\s+-R\s+777\s+/",
]
MAX_SHELL_TIMEOUT = int(os.getenv("ENGOLA_SHELL_TIMEOUT", "120"))
HISTORY_TURNS = int(os.getenv("ENGOLA_HISTORY_TURNS", "16"))
KNOWLEDGE_TOP_K = int(os.getenv("ENGOLA_KNOWLEDGE_TOP_K", "5"))

SYSTEM_PROMPT = (
    f"You are Engola, {OWNER_NAME}'s private personal assistant, running on his own "
    f"device. Be direct, concise and useful -- no filler, no AI disclaimers unless "
    f"relevant. If you don't know something current, say so rather than guessing. "
    f"You have real tools on this device: web search, shell/device control, email, "
    f"and a persistent memory of past conversations that gets retrieved and given to "
    f"you as context below when relevant -- use it naturally, don't just repeat it back."
)


def require(name: str, value: str) -> None:
    if not value:
        raise SystemExit(f"Missing required env var: {name}. Copy .env.example to .env and fill it in.")
