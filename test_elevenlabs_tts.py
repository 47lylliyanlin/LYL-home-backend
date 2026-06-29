import asyncio
from pathlib import Path

from api.tts import text_to_speech


async def main() -> None:
    text = "你好，我是 Kiro。现在我正在用 ElevenLabs 说话。"
    output_path = await text_to_speech(text)
    print(f"[OK] ElevenLabs TTS generated: {Path(output_path).resolve()}")


if __name__ == "__main__":
    asyncio.run(main())