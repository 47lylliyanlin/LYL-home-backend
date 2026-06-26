# Voice + ElevenLabs + Bilingual Reply Work Outline

Date: 2026-06-27
Scope: Backend voice output, ElevenLabs TTS, bilingual display, and debugging notes.

## 1. Goal

This round of work focused on improving Kiro's voice experience:

- Replace temporary/local TTS usage with ElevenLabs.
- Keep the existing frontend API contract mostly compatible.
- Make Kiro speak English audio through ElevenLabs.
- Show bilingual text in the chat UI: English first, Chinese below.
- Prepare the code and documentation so the project can be maintained without needing to rediscover the voice flow.

## 2. Current Voice Flow

### Text chat

1. User sends text from frontend.
2. Backend calls `prepare_chat_turn()` to inject memory context.
3. Backend calls the active AI model through `api.ai_client.chat_completion()`.
4. Backend asks the model to return bilingual marked text.
5. Backend returns:
   - `reply`: display fallback text
   - `reply_en`: English reply
   - `reply_zh`: Chinese translation
   - `reply_parts`: structured bilingual subtitle units
6. Frontend renders `reply_parts` when present.

### Voice chat

1. User records audio in the frontend.
2. Backend receives `/api/voice-chat` upload.
3. Backend uses Whisper STT through `api/stt.py`.
4. Backend generates bilingual reply through the active model.
5. Backend sends only the English text to ElevenLabs.
6. ElevenLabs returns MP3 bytes.
7. Backend saves the MP3 to `audio/output/tts_*.mp3`.
8. Backend returns text and audio URL to the frontend.
9. Frontend shows bilingual text and a playback bar.

## 3. Files Touched Or Introduced

### Backend

- `api/tts.py`
  - Replaced Edge TTS with ElevenLabs HTTP API usage.
  - Reads `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, and optional tuning variables from `.env`.
  - Saves generated MP3 files under `audio/output`.

- `test_elevenlabs_tts.py`
  - Simple local smoke test for ElevenLabs TTS.
  - Generates one MP3 using the configured voice.

- `.env.example`
  - Documents ElevenLabs variables.
  - Also documents the multi-model AI routing variables added by the other workstream.

- `main.py`
  - Added bilingual response shaping.
  - Voice chat now sends English-only text to ElevenLabs.
  - API responses include structured bilingual fields.

- `api/ai_client.py`
  - Unified AI routing used by chat and memory extraction.
  - Supports provider/profile switching through `.env`.

### Frontend

- `frontend/index.html`
  - Added bilingual subtitle-style rendering when structured parts are returned.
  - English and Chinese have different visual treatment.
  - Existing playback controls were left unchanged.

### Docs

- `docs/VOICE_SETUP.md`
  - User-facing setup guide for ElevenLabs.

## 4. Environment Variables

Required for ElevenLabs:

```env
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
```

Optional ElevenLabs tuning:

```env
ELEVENLABS_STABILITY=0.5
ELEVENLABS_SIMILARITY_BOOST=0.75
ELEVENLABS_STYLE=0.0
ELEVENLABS_USE_SPEAKER_BOOST=true
```

Active model routing example:

```env
AI_ACTIVE_PROFILE=GEMINI
AI_GEMINI_PROVIDER=gemini_native
AI_GEMINI_API_KEY=your_gemini_key_here
AI_GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta
AI_GEMINI_MODEL=gemini-flash-latest
```

## 5. Testing Done

- Ran `python test_elevenlabs_tts.py` successfully after adding ElevenLabs API key and voice ID.
- Verified local backend health endpoint: `http://localhost:8000/`.
- Verified local frontend can be served from `http://localhost:8080`.
- Verified Python syntax with `venv\Scripts\python.exe -m py_compile main.py`.

## 6. Issues Found During Testing

### Duplicate backend processes

Several times, both of these were running:

```text
F:\kiro-project\backend\venv\Scripts\python.exe main.py
C:\Program Files\Python311\python.exe main.py
```

This caused old code to keep serving port `8000`, making fixes appear not to work.

Recommended habit:

```powershell
Get-CimInstance Win32_Process -Filter "name = 'python.exe'" | Select-Object ProcessId,CommandLine
```

Only one backend `main.py` process should be running.

### Gemini quota usage

Gemini returned:

```text
429 RESOURCE_EXHAUSTED
Quota exceeded for generate_content_free_tier_requests
```

This is a request quota issue, not an ElevenLabs issue.

Reasons usage is high:

- One user message can trigger model reply generation.
- Bilingual format repair can trigger another model request if the first response is malformed.
- Memory extraction can trigger another model request after the reply.
- Memory context makes prompts large.

## 7. Recommended Next Steps

1. Add a `KIRO_TEST_MODE=true` switch for cheaper testing.
2. In test mode:
   - reduce recent-turn context from 10 to 3
   - disable memory extraction
   - avoid second-pass bilingual repair unless necessary
3. Add a backend `/api/debug/token-estimate` endpoint or log summary.
4. Clean duplicate server startup workflow.
5. Consider splitting voice testing from memory-heavy conversation testing.