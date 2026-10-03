"""Full-text search across every daily transcript ever written
(data/transcripts/*.md), so Engola can recall things from any point in its
history -- not just the last HISTORY_TURNS exchanges kept in the live
context window. Simple keyword-overlap scoring, entirely local, no API
calls, no embeddings needed.

Honest limitation: this is keyword matching, not semantic search. It will
miss relevant past exchanges phrased very differently from the current
question, and can surface irrelevant ones that happen to share common
words. A proper upgrade path exists using the Gemini embedding model
already configured in config.py (GEMINI_EMBED_MODEL) for real semantic
similarity -- not built here, flagged as a future improvement."""
import re

import config

_WORD_RE = re.compile(r"[a-zA-Z0-9]{3,}")
_STOPWORDS = {"the", "and", "for", "you", "your", "was", "were", "with", "have",
              "this", "that", "what", "did", "are", "can", "not", "but"}


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text)} - _STOPWORDS


def search(query: str, top_k: int = 3, max_chars: int = 700) -> list[str]:
    q_words = _tokenize(query)
    if not q_words:
        return []

    scored = []
    for path in sorted(config.LOG_DIR.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        blocks = re.split(r"(?=^### \d{2}:\d{2}:\d{2})", text, flags=re.M)
        for block in blocks:
            words = _tokenize(block)
            overlap = len(q_words & words)
            if overlap > 0:
                scored.append((overlap, path.name, block.strip()))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [f"[{fname}]\n{block[:max_chars]}" for _, fname, block in scored[:top_k]]


def as_context_block(query: str) -> str:
    excerpts = search(query)
    if not excerpts:
        return ""
    joined = "\n\n---\n\n".join(excerpts)
    return (
        "SYSTEM NOTICE -- verbatim excerpts retrieved from real past transcripts "
        "(not a summary, not a guess). Use only what is actually relevant to the "
        "current message; ignore the rest:\n\n" + joined
    )
