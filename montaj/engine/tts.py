"""Voice-over with ElevenLabs text-to-speech (needs the user's ElevenLabs API key)."""

import hashlib
from pathlib import Path

import httpx2

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # "Rachel", a premade multilingual voice
MODEL = "eleven_multilingual_v2"  # speaks Romanian


class TTSError(RuntimeError):
    pass


def synthesize(text: str, dest_dir: Path, api_key: str, voice: str | None = None) -> Path:
    """MP3 for one line, cached by text + voice."""
    voice = voice or DEFAULT_VOICE
    dest_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{voice}|{MODEL}|{text}".encode()).hexdigest()[:16]
    dest = dest_dir / f"vo_{key}.mp3"
    if dest.exists():
        return dest
    try:
        r = httpx2.post(API.format(voice=voice), params={"output_format": "mp3_44100_128"},
                        headers={"xi-api-key": api_key, "accept": "audio/mpeg"},
                        json={"text": text, "model_id": MODEL}, timeout=120)
    except httpx2.HTTPError as exc:
        raise TTSError(f"Nu mă pot conecta la ElevenLabs: {exc}") from exc
    if r.status_code == 401:
        raise TTSError("Cheia ElevenLabs nu e validă (Setări).")
    if r.status_code >= 400:
        raise TTSError(f"ElevenLabs a răspuns cu eroare {r.status_code}: {r.text[:200]}")
    dest.write_bytes(r.content)
    return dest
