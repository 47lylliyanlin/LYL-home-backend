from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from api.stt import transcribe_audio
from api.tts import text_to_speech
from api.memory import get_memory_summary
from api.gateway import prepare_chat_turn, consolidate_chat_turn, get_last_injected_context
from api.profile import profile_manager
from api.memory_graph import graph_status
from api.word_map import load_word_map, rebuild_word_map
from api.darkroom import darkroom_status, enter_darkroom_note
from api.dream import dream_light_status, run_dream_light, run_memory_maintenance
from api.pulse import introspection_status, pulse_status
from api.ai_client import active_ai_config, chat_completion, chat_messages
from api.security import admin_auth_middleware, cors_origins
import os
from pathlib import Path
from typing import List

app = FastAPI()

# Protect Dashboard and administrative/debug endpoints when KIRO_ADMIN_TOKEN is set.
app.middleware("http")(admin_auth_middleware)

# CORS support for the frontend. Set KIRO_CORS_ORIGINS for cloud deployments.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files.
app.mount("/audio/output", StaticFiles(directory="audio/output"), name="audio_output")
app.mount("/audio/input", StaticFiles(directory="audio/input"), name="audio_input")
app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")

print("Checking memory system...")
memory_context_preview = get_memory_summary()
print(f"Memory system ready, startup preview length={len(memory_context_preview)}")


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    recent_turns_count: int = 4
    recent_char_limit: int = 180


class ProfileCandidateRequest(BaseModel):
    title: str
    content: str
    evidence_ids: List[str] = []
    confidence: float = 0.5
    source: str = "manual"


class ProfileCandidateReviewRequest(BaseModel):
    reviewer: str = "manual"
    reason: str = ""


class DarkroomNoteRequest(BaseModel):
    content: str
    reason: str = "internal_reflection"


@app.get("/")
def read_root():
    return {"message": "Hello, I am Kiro backend service"}


@app.get("/api/gateway/last-context")
def last_gateway_context():
    """Return the last context injected by Ombre Gateway for debugging."""
    return get_last_injected_context()




@app.get("/api/profile")
def get_profile_state():
    """Return current profile documents for debugging and future dashboard use."""
    return profile_manager.get_profiles()


@app.get("/api/profile/candidates")
def get_profile_candidates():
    """Return profile fact candidates. Candidates are not confirmed facts."""
    return {"candidates": profile_manager.list_candidates()}





@app.post("/api/profile/candidates")
def create_profile_candidate(request: ProfileCandidateRequest):
    """Create a profile fact candidate. This does not confirm it as profile fact."""
    path = profile_manager.create_candidate(
        title=request.title,
        content=request.content,
        evidence_ids=request.evidence_ids,
        confidence=request.confidence,
        source=request.source,
    )
    return {"ok": True, "file": str(path), "status": "candidate" if request.evidence_ids else "pending_evidence"}


@app.post("/api/profile/candidates/{candidate_name}/approve")
def approve_profile_candidate(candidate_name: str, request: ProfileCandidateReviewRequest):
    """Promote a reviewed profile candidate into User Portrait."""
    try:
        return profile_manager.approve_candidate(candidate_name, reviewer=request.reviewer)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="candidate not found")


@app.post("/api/profile/candidates/{candidate_name}/reject")
def reject_profile_candidate(candidate_name: str, request: ProfileCandidateReviewRequest):
    """Reject a profile candidate without promoting it."""
    try:
        return profile_manager.reject_candidate(candidate_name, reviewer=request.reviewer, reason=request.reason)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="candidate not found")


@app.get("/api/memory/graph/status")
def get_memory_graph_status():
    """Return lightweight memory graph status for debugging."""
    return graph_status()



@app.get("/api/memory/word-map")
def get_word_map():
    """Return Word Map Lite. Observational only, not evidence."""
    return load_word_map()


@app.post("/api/memory/word-map/rebuild")
def rebuild_word_map_endpoint():
    """Rebuild Word Map Lite from current buckets and moments."""
    return rebuild_word_map()




@app.get("/api/darkroom/status")
def get_darkroom_status():
    """Return Darkroom door state only. Note bodies are not exposed."""
    return darkroom_status()


@app.post("/api/darkroom/enter")
def enter_darkroom(request: DarkroomNoteRequest):
    """Write a private Darkroom note. Returns metadata only, never the body."""
    return enter_darkroom_note(request.content, reason=request.reason)




@app.get("/api/dream/light/status")
def get_dream_light_status():
    """Return Dream Light state. Does not expose Darkroom note bodies."""
    return dream_light_status()


@app.post("/api/dream/light/run")
def run_dream_light_endpoint():
    """Run Dream Light shallow digestion."""
    return run_dream_light()




@app.post("/api/maintenance/run")
def run_maintenance_endpoint():
    """Run safe memory maintenance: Word Map rebuild plus Dream Light."""
    return run_memory_maintenance()




@app.get("/api/pulse")
def get_pulse_status():
    """Read-only memory system pulse."""
    return pulse_status()


@app.get("/api/introspection")
def get_introspection_status():
    """Read-only introspection summary for debugging and future dashboard use."""
    return introspection_status()


@app.get("/api/ai/config")
def get_ai_config():
    """Return active AI routing config without exposing API keys."""
    return active_ai_config()




def _between_markers(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        return ""
    start += len(start_marker)
    end = text.find(end_marker, start)
    if end < 0:
        end = len(text)
    return text[start:end].strip()


def _format_bilingual_reply(english: str, chinese: str) -> str:
    english = (english or "").strip()
    chinese = (chinese or "").strip()
    if english and chinese:
        return f"{english}\n{chinese}"
    return english or chinese

def _split_paragraphs(text: str) -> list[str]:
    return [part.strip() for part in (text or "").split("\n") if part.strip()]


def _bilingual_parts(english: str, chinese: str) -> list[dict]:
    english_parts = _split_paragraphs(english)
    chinese_parts = _split_paragraphs(chinese)
    total = max(len(english_parts), len(chinese_parts))
    parts = []
    for index in range(total):
        parts.append({
            "english": english_parts[index] if index < len(english_parts) else "",
            "chinese": chinese_parts[index] if index < len(chinese_parts) else "",
        })
    return parts


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text or "")


def _looks_like_english(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    cjk = sum("\u4e00" <= char <= "\u9fff" for char in stripped)
    ascii_letters = sum(("a" <= char.lower() <= "z") for char in stripped)
    return ascii_letters > 0 and cjk == 0


def _parse_marked_bilingual(text: str) -> dict:
    return {
        "english": _between_markers(text, "<<<ENGLISH>>>", "<<<CHINESE>>>"),
        "chinese": _between_markers(text, "<<<CHINESE>>>", "<<<END>>>"),
    }


def _repair_bilingual_reply(raw_reply: str) -> dict:
    repair_prompt = f"""Convert the following Kiro reply into bilingual display text.

Rules:
- Keep the meaning, warmth, and emotional nuance.
- The English line must be natural conversational English and contain no Chinese characters.
- The Chinese line must be natural Simplified Chinese.
- Break longer replies into matching short subtitle units: each English unit on its own line, and the corresponding Chinese unit on the same line number.
- Return exactly this marker format, with no extra text:
<<<ENGLISH>>>
English text here
<<<CHINESE>>>
Chinese translation here
<<<END>>>

Original reply:
{raw_reply}
"""
    repaired = chat_completion(
        system_prompt="You convert replies into bilingual marker format. Follow the requested markers exactly.",
        user_message=repair_prompt,
        max_tokens=512,
    )
    return _parse_marked_bilingual(repaired)


def generate_bilingual_reply(system_prompt: str, user_message: str, messages: List[dict] = None) -> dict:
    """Generate an English voice line plus a Chinese translation for display."""
    bilingual_system_prompt = f"""{system_prompt}

Output format override:
- Reply naturally as Kiro, preserving the personality and memory guidance above.
- The spoken reply must be English only and contain no Chinese characters.
- Also provide a faithful, natural Simplified Chinese translation for display.
- Break longer replies into matching short subtitle units: each English unit on its own line, and the corresponding Chinese unit on the same line number.
- Return exactly this marker format, with no JSON and no markdown:
<<<ENGLISH>>>
English text here
<<<CHINESE>>>
Chinese translation here
<<<END>>>
"""
    raw_reply = chat_messages(
        system_prompt=bilingual_system_prompt,
        messages=messages or [{"role": "user", "content": user_message}],
        max_tokens=1024,
    )

    parsed = _parse_marked_bilingual(raw_reply)
    english = parsed["english"]
    chinese = parsed["chinese"]

    if not _looks_like_english(english) or not chinese:
        repaired = _repair_bilingual_reply(raw_reply)
        english = repaired["english"] or english
        chinese = repaired["chinese"] or chinese

    if not chinese and _contains_cjk(raw_reply):
        chinese = raw_reply.strip()

    display_text = _format_bilingual_reply(english, chinese)
    return {
        "english": english or display_text,
        "chinese": chinese,
        "display": display_text,
        "parts": _bilingual_parts(english, chinese),
    }

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Text chat through Ombre Gateway."""
    try:
        prepared = prepare_chat_turn(
            request.message,
            session_id=request.session_id,
            recent_turns_count=request.recent_turns_count,
            recent_char_limit=request.recent_char_limit,
        )

        chinese_system_prompt = f"""{prepared.system_prompt}

Output language override:
- Reply in Simplified Chinese only.
- Do not include English unless the user explicitly asks for English wording.
- Keep Kiro's warmth, memory, and natural tone.
"""
        reply_text = chat_messages(
            system_prompt=chinese_system_prompt,
            messages=prepared.messages,
            max_tokens=1024,
        )

        try:
            await consolidate_chat_turn(request.message, reply_text, session_id=request.session_id)
        except Exception as mem_error:
            print(f"Memory consolidation failed: {mem_error}")

        return {"reply": reply_text}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/tts")
async def tts(request: ChatRequest):
    """Text to speech."""
    try:
        audio_path = await text_to_speech(request.message)
        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            filename="output.mp3"
        )
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/voice-chat")
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: str = Form("default"),
    recent_turns_count: int = Form(4),
    recent_char_limit: int = Form(180),
):
    """Voice chat: receive audio, return text and audio reply."""
    try:
        import time
        timestamp = str(int(time.time() * 1000))
        audio_filename = f"user_{timestamp}.wav"
        audio_path = f"audio/input/{audio_filename}"
        os.makedirs("audio/input", exist_ok=True)

        with open(audio_path, "wb") as f:
            content = await audio.read()
            f.write(content)

        user_text = transcribe_audio(audio_path)
        prepared = prepare_chat_turn(
            user_text,
            session_id=session_id,
            recent_turns_count=recent_turns_count,
            recent_char_limit=recent_char_limit,
        )

        reply = generate_bilingual_reply(prepared.system_prompt, user_text, prepared.messages)
        assistant_text = reply["display"]
        assistant_audio_text = reply["english"]

        audio_output_path = await text_to_speech(assistant_audio_text)

        try:
            await consolidate_chat_turn(user_text, assistant_text, session_id=session_id)
        except Exception as mem_error:
            print(f"Memory consolidation failed: {mem_error}")

        return {
            "user_audio_url": f"/audio/input/{audio_filename}",
            "user_text": user_text,
            "assistant_text": assistant_text,
            "assistant_text_en": reply["english"],
            "assistant_text_zh": reply["chinese"],
            "assistant_audio_text": assistant_audio_text,
            "assistant_text_parts": reply["parts"],
            "assistant_audio_url": f"/audio/output/{os.path.basename(audio_output_path)}"
        }

    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
