"""
Speech-to-text module.

Local Whisper is optional. Cloud deployments can leave STT_PROVIDER=disabled so
text chat and ElevenLabs TTS work without installing torch/openai-whisper.
"""

import os
from pathlib import Path
from typing import Any


_BACKEND_DIR = Path(__file__).resolve().parents[1]
_model: Any = None


def _load_dotenv_once() -> None:
    env_path = _BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        return


_load_dotenv_once()


def _stt_provider() -> str:
    return os.getenv("STT_PROVIDER", "disabled").strip().lower()


def _get_whisper_model():
    global _model
    if _model is not None:
        return _model

    try:
        import whisper
    except ImportError as exc:
        raise RuntimeError(
            "Local Whisper STT is not installed. Install local voice dependencies "
            "or set STT_PROVIDER=disabled for cloud text-only deployment."
        ) from exc

    ffmpeg_path = os.getenv("FFMPEG_BIN_DIR")
    if ffmpeg_path:
        os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ.get("PATH", "")

    model_name = os.getenv("WHISPER_MODEL", "small")
    _model = whisper.load_model(model_name)
    return _model


def transcribe_audio(audio_path: str) -> str:
    """Convert an audio file to text when a configured STT provider is available."""
    provider = _stt_provider()
    if provider in {"", "disabled", "none", "off"}:
        raise RuntimeError("Voice input is disabled on this deployment. Set STT_PROVIDER=whisper to enable local STT.")

    if provider != "whisper":
        raise RuntimeError(f"Unsupported STT_PROVIDER: {provider}")

    try:
        result = _get_whisper_model().transcribe(audio_path, language=os.getenv("STT_LANGUAGE", "zh"))
        return result["text"]
    except Exception as e:
        raise RuntimeError(f"Speech recognition failed: {str(e)}") from e
