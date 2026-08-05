"""CouncilKey-Os Voice - TTS + transcription (real implementation).

TTS providers (in order of preference):
- Edge TTS  (free, no key, default)      -> mp3
- ElevenLabs (ELEVENLABS_API_KEY)        -> mp3
- OpenAI TTS (OPENAI_API_KEY)            -> mp3

Transcription:
- OpenAI Whisper local model (openai-whisper package, free, offline)
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

COUNCIL_HOME = Path(os.environ.get("COUNCIL_HOME", "/var/lib/council"))
AUDIO_DIR = COUNCIL_HOME / "shared" / "audio"

EDGE_VOICES = {
    "en-US": "en-US-JennyNeural",
    "en-GB": "en-GB-SoniaNeural",
    "hi-IN": "hi-IN-SwaraNeural",
    "ta-IN": "ta-IN-PallaviNeural",
    "te-IN": "te-IN-ShrutiNeural",
}


def _new_path(prefix: str, ext: str) -> Path:
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    return AUDIO_DIR / f"{prefix}-{ts}.{ext}"


def voice_status() -> dict[str, Any]:
    """Report which voice providers are available right now."""
    providers = {
        "edge_tts": _import_ok("edge_tts"),
        "elevenlabs": bool(os.environ.get("ELEVENLABS_API_KEY")),
        "openai_tts": bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("VOICE_TOOLS_OPENAI_KEY")),
        "whisper_local": _import_ok("whisper"),
    }
    return {"providers": providers, "default": "edge" if providers["edge_tts"] else "none"}


def _import_ok(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def tts(text: str, voice: str | None = None, provider: str = "edge") -> dict[str, Any]:
    """Synthesize speech for `text` and save it under shared/audio."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "empty text"}
    provider = (provider or "edge").lower()

    if provider == "edge":
        return _tts_edge(text, voice)
    if provider == "eleven":
        return _tts_elevenlabs(text, voice)
    if provider == "openai":
        return _tts_openai(text, voice)
    return {"ok": False, "error": f"unknown provider {provider!r}"}


def _tts_edge(text: str, voice: str | None) -> dict[str, Any]:
    try:
        import edge_tts  # type: ignore
    except Exception:
        return {"ok": False, "error": "edge-tts not installed (pip install edge-tts) - free default TTS"}
    v = voice or EDGE_VOICES.get("en-US", "en-US-JennyNeural")
    out = _new_path("tts", "mp3")
    try:
        import asyncio

        async def _run() -> None:
            comm = edge_tts.Communicate(text, v)
            await comm.save(str(out))

        asyncio.run(_run())
        return {"ok": True, "path": str(out), "name": out.name, "bytes": out.stat().st_size, "provider": "edge", "voice": v}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _tts_elevenlabs(text: str, voice: str | None) -> dict[str, Any]:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        return {"ok": False, "error": "ELEVENLABS_API_KEY not set"}
    out = _new_path("tts", "mp3")
    try:
        r = requests_post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice or '21m00Tcm4TlvDq8ikWAM'}",
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_multilingual_v2"},
            timeout=60,
        )
        r.raise_for_status()
        out.write_bytes(r.content)
        return {"ok": True, "path": str(out), "name": out.name, "bytes": len(r.content), "provider": "elevenlabs"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _tts_openai(text: str, voice: str | None) -> dict[str, Any]:
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("VOICE_TOOLS_OPENAI_KEY")
    if not key:
        return {"ok": False, "error": "OPENAI_API_KEY not set"}
    out = _new_path("tts", "mp3")
    try:
        r = requests_post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "tts-1", "voice": voice or "alloy", "input": text},
            timeout=60,
        )
        r.raise_for_status()
        out.write_bytes(r.content)
        return {"ok": True, "path": str(out), "name": out.name, "bytes": len(r.content), "provider": "openai"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def requests_post(url: str, **kwargs: Any) -> Any:
    import httpx

    return httpx.post(url, **kwargs)


def transcribe(audio_path: str) -> dict[str, Any]:
    """Transcribe an audio file with local Whisper (free, offline)."""
    p = Path(audio_path)
    if not p.exists():
        return {"ok": False, "error": f"file not found: {audio_path}"}
    try:
        import whisper  # type: ignore
    except Exception:
        return {"ok": False, "error": "openai-whisper not installed (pip install openai-whisper)"}
    try:
        model = whisper.load_model("base")
        result = model.transcribe(str(p))
        text = (result.get("text") or "").strip()
        return {"ok": True, "text": text, "language": result.get("language", "")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def voice_chat_flow() -> dict[str, str]:
    """Documentation of the voice flow (for UI/agents)."""
    return {
        "flow": "browser mic -> transcription (whisper or browser API) -> council ask -> TTS reply -> play audio",
        "endpoints": {
            "/api/voice/tts": "POST text -> mp3 (Edge/ElevenLabs/OpenAI)",
            "/api/voice/transcribe": "POST audio file -> text (local Whisper)",
        },
    }


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        print(json.dumps(tts(sys.argv[1]), indent=2))
    else:
        print(json.dumps(voice_status(), indent=2))
