"""
TTS (Text-to-Speech) module.

Uses ElevenLabs to convert assistant text into an MP3 file saved under
audio/output so the existing FastAPI static file URLs keep working.
"""

from datetime import datetime
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")

OUTPUT_DIR = "audio/output"
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"


def _get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_payload(text: str) -> dict[str, Any]:
    model_id = os.getenv("ELEVENLABS_MODEL_ID", DEFAULT_MODEL_ID)
    stability = float(os.getenv("ELEVENLABS_STABILITY", "0.5"))
    similarity_boost = float(os.getenv("ELEVENLABS_SIMILARITY_BOOST", "0.75"))
    style = float(os.getenv("ELEVENLABS_STYLE", "0.0"))
    use_speaker_boost = os.getenv("ELEVENLABS_USE_SPEAKER_BOOST", "true").lower() == "true"

    return {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": use_speaker_boost,
        },
    }


async def text_to_speech_async(text: str, output_path: str | None = None) -> str:
    """
    Convert text to speech with ElevenLabs and return the generated audio path.
    """
    if not text or not text.strip():
        raise ValueError("TTS text cannot be empty")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = os.path.join(OUTPUT_DIR, f"tts_{timestamp}.mp3")

    api_key = _get_required_env("ELEVENLABS_API_KEY")
    voice_id = _get_required_env("ELEVENLABS_VOICE_ID")
    output_format = os.getenv("ELEVENLABS_OUTPUT_FORMAT", DEFAULT_OUTPUT_FORMAT)

    url = f"{ELEVENLABS_API_URL}/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    params = {"output_format": output_format}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            url,
            headers=headers,
            params=params,
            json=_build_payload(text),
        )

    if response.status_code >= 400:
        raise RuntimeError(f"ElevenLabs TTS failed: {response.status_code} {response.text}")

    with open(output_path, "wb") as audio_file:
        audio_file.write(response.content)

    return output_path


text_to_speech = text_to_speech_async
