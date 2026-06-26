# Maintainable Backend Notes For Voice And Bilingual Replies

Date: 2026-06-27
Audience: Future maintainers of `F:\kiro-project\backend`.

## 1. Backend Responsibility Map

### `main.py`

Owns HTTP routes and response assembly.

Important routes:

- `POST /api/chat`
  - text-only chat
  - returns bilingual display fields

- `POST /api/voice-chat`
  - receives user audio
  - runs STT
  - generates bilingual response
  - sends English-only text to TTS
  - returns audio URL

- `POST /api/tts`
  - direct text-to-speech endpoint
  - useful for manual testing

### `api/tts.py`

Owns ElevenLabs integration.

Expected behavior:

- Read `.env` from backend root.
- Require `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID`.
- Call ElevenLabs text-to-speech endpoint.
- Save MP3 to `audio/output`.
- Return the local output file path.

Do not put API keys in code.

### `api/ai_client.py`

Owns active AI model routing.

Expected behavior:

- Read active profile from `AI_ACTIVE_PROFILE`.
- Resolve provider-specific variables like `AI_GEMINI_API_KEY` or `AI_CLAUDE_API_KEY`.
- Expose a common `chat_completion()` function.
- Expose `json_completion()` for memory extraction.

### `api/gateway.py`

Owns memory-context preparation and post-turn consolidation.

Important functions:

- `prepare_chat_turn(user_message)`
- `consolidate_chat_turn(user_message, assistant_message)`

This module can greatly increase token usage because it injects memory/profile/recent-turn context.

### `api/memory_extraction.py`

Owns post-conversation memory extraction.

This can trigger an additional model call per user message.

## 2. Bilingual Reply Design

The current intended behavior is:

```text
English subtitle unit
对应中文翻译

Next English subtitle unit
对应中文翻译
```

Backend should return:

```json
{
  "reply": "fallback display text",
  "reply_en": "English text",
  "reply_zh": "Chinese text",
  "reply_parts": [
    {
      "english": "English subtitle unit",
      "chinese": "对应中文翻译"
    }
  ]
}
```

Voice chat should additionally return:

```json
{
  "assistant_text": "fallback display text",
  "assistant_text_en": "English text",
  "assistant_text_zh": "Chinese text",
  "assistant_audio_text": "English text used for ElevenLabs",
  "assistant_text_parts": [
    {
      "english": "English subtitle unit",
      "chinese": "对应中文翻译"
    }
  ],
  "assistant_audio_url": "/audio/output/tts_xxx.mp3"
}
```

Important rule:

```text
ElevenLabs should receive English only.
```

## 3. Recommended Backend Helpers

Keep bilingual parsing small and defensive.

Suggested helper responsibilities:

- Extract text between markers.
- Check whether English contains Chinese characters.
- Split English and Chinese into matching subtitle units.
- Return structured `parts` for the frontend.

Avoid relying on raw JSON from weaker/free models if the model often returns unescaped strings. Marker format is more forgiving during development.

## 4. Token And Quota Maintenance

The current request can be expensive because one user turn may trigger:

1. Main reply generation.
2. Bilingual repair generation if the first response is malformed.
3. Memory extraction after the reply.

The prompt can also be large because `prepare_chat_turn()` may include:

- profile wake context
- relationship weather
- darkroom door state
- wake anchors
- recent turns
- scene memories
- graph diffusion
- word map hints

### Recommended test mode

Add this to `.env`:

```env
KIRO_TEST_MODE=true
```

When enabled, recommended behavior:

- Do not run memory extraction.
- Use fewer recent turns, for example 3 instead of 10.
- Skip bilingual repair unless the English text is missing or contains Chinese.
- Optionally return model usage estimates in logs.

### Recommended production mode

```env
KIRO_TEST_MODE=false
```

Production can restore:

- memory extraction
- deeper context
- stronger bilingual repair
- richer continuity

## 5. Local Runbook

### Start backend

```powershell
cd F:\kiro-project\backend
venv\Scripts\activate
python main.py
```

Health check:

```powershell
Invoke-WebRequest http://localhost:8000/ -UseBasicParsing
```

Expected response:

```json
{"message":"Hello, I am Kiro backend service"}
```

### Start frontend

```powershell
cd F:\kiro-project\backend
python -m http.server 8080 --directory ../frontend
```

Open:

```text
http://localhost:8080
```

### Check duplicate Python servers

```powershell
Get-CimInstance Win32_Process -Filter "name = 'python.exe'" | Select-Object ProcessId,CommandLine
```

If more than one `main.py` is running, stop the stale ones before testing.

## 6. Security Notes

Never commit:

- `.env`
- API keys
- runtime conversation logs
- private memory files unless intentionally reviewed
- generated audio files

Safe to commit:

- `.env.example`
- docs
- code changes without secrets

## 7. Future Refactor Suggestions

1. Move bilingual helpers from `main.py` into `api/reply_format.py`.
2. Move route logic into `api/routes/chat.py` once the app grows.
3. Add structured logging for model call count per user turn.
4. Add a token/request budget display in the dashboard.
5. Add a single `scripts/start_dev.ps1` to prevent duplicate backend processes.
6. Add tests for bilingual parsing and ElevenLabs text selection.