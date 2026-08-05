"""
CouncilKey-Os Voice Chat with ElevenLabs TTS + Whisper Transcription - Advanced Production
Voice memo transcription, cross-platform conversation continuity, talk to Hermes and hear back
"""

import os
from pathlib import Path

def voice_chat_tools():
    return [
        {
            "provider": "Edge TTS",
            "env": "None",
            "free": "Yes default",
            "use": "Text to voice for dashboard chat, talk to Hermes and hear back, cross-platform conversation continuity - Free, no API key, default in Hermes",
            "how": "Edge TTS via edge-tts Python package, no API key needed, free default"
        },
        {
            "provider": "ElevenLabs",
            "env": "ELEVENLABS_API_KEY",
            "free": "Free tier - 10k chars/month free",
            "use": "Better voice, more natural, voice cloning, cross-platform",
            "how": "ElevenLabs API with api key from env ELEVENLABS_API_KEY, from secrets/ GPG encrypted"
        },
        {
            "provider": "OpenAI TTS",
            "env": "VOICE_TOOLS_OPENAI_KEY",
            "free": "Paid - $0.015 per 1k chars",
            "use": "OpenAI TTS tts-1 and tts-1-hd, high quality",
            "how": "OpenAI API key"
        },
        {
            "provider": "Whisper",
            "env": "None local",
            "free": "Free - local model",
            "use": "Voice memo transcription, talk to Hermes and hear back, cross-platform conversation continuity, Telegram/Discord/Signal voice memo transcription",
            "how": "OpenAI Whisper local model 20250625, openai-whisper Python package, no API key, local, privacy"
        },
        {
            "provider": "Kokoro",
            "env": "None local",
            "free": "Free local",
            "use": "Local TTS, no API key, privacy, fast",
            "how": "Kokoro TTS local model, kokoro package, no API key, local"
        }
    ]

def voice_chat_flow():
    """
    Voice chat flow:
    1. User speaks into microphone (browser getUserMedia)
    2. Audio captured as blob
    3. Transcription via Whisper local or API
    4. Text goes to council ask (together or alone)
    5. Council responds with text
    6. TTS via Edge TTS or ElevenLabs converts text to audio
    7. Audio played back to user
    8. Cross-platform: Telegram/Discord/Signal voice memo transcription same flow
    """
    return {
        "flow": [
            "User speaks into microphone (browser getUserMedia API, waveform visualization)",
            "Audio captured as blob, sent to backend /api/voice/transcribe via WebSocket or POST",
            "Transcription via Whisper local (openai-whisper 20250625) or API (if internet)",
            "Text goes to council ask together or alone: council ask 'transcribed text'",
            "Council responds with text (3 agents debate+vote or solo)",
            "TTS via Edge TTS (free default) or ElevenLabs (better voice) converts text to audio",
            "Audio played back to user via <audio> element, waveform visualization",
            "Cross-platform: Telegram/Discord/Signal voice memo transcription same flow, gateway handles voice memo transcription"
        ],
        "endpoints": {
            "/api/voice/transcribe": "POST audio blob -> text via Whisper",
            "/api/voice/tts": "POST text -> audio blob via Edge TTS or ElevenLabs",
            "/ws/voice": "WebSocket for real-time voice chat, bidirectional audio + text"
        }
    }

if __name__ == "__main__":
    import json
    print(json.dumps(voice_chat_tools(), indent=2))
    print(json.dumps(voice_chat_flow(), indent=2))
