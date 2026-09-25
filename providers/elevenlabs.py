"""ElevenLabs text-to-speech client, used by /speak."""
import requests

import config

BASE_URL = "https://api.elevenlabs.io/v1"


def configured() -> bool:
    return bool(config.ELEVENLABS_API_KEY and config.ELEVENLABS_VOICE_ID)


def list_voices() -> list[dict]:
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ElevenLabs is not configured (ELEVENLABS_API_KEY unset)")
    r = requests.get(f"{BASE_URL}/voices", headers={"xi-api-key": config.ELEVENLABS_API_KEY}, timeout=15)
    r.raise_for_status()
    return [{"voice_id": v["voice_id"], "name": v["name"]} for v in r.json().get("voices", [])]


def synthesize(text: str, voice_id: str = "", model_id: str = "eleven_turbo_v2_5") -> bytes:
    if not config.ELEVENLABS_API_KEY:
        raise RuntimeError("ElevenLabs is not configured (ELEVENLABS_API_KEY unset)")
    voice = (voice_id or config.ELEVENLABS_VOICE_ID).strip()
    if not voice:
        raise RuntimeError(
            "No ElevenLabs voice selected. Run /voices to list options, then set ELEVENLABS_VOICE_ID."
        )
    text = (text or "").strip()[:5000]
    if not text:
        raise RuntimeError("Nothing to speak")

    r = requests.post(
        f"{BASE_URL}/text-to-speech/{voice}",
        json={"text": text, "model_id": model_id, "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
        headers={"xi-api-key": config.ELEVENLABS_API_KEY, "Accept": "audio/mpeg"},
        timeout=45,
    )
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs synthesis failed ({r.status_code}): {r.text[:300]}")
    return r.content
