from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
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
import os
from pathlib import Path
from typing import List

app = FastAPI()

# CORS support for the local frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files.
app.mount("/audio/output", StaticFiles(directory="audio/output"), name="audio_output")
app.mount("/audio/input", StaticFiles(directory="audio/input"), name="audio_input")
app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")

# Claude API client. Configure with environment variables.
claude_client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
)

print("Checking memory system...")
memory_context_preview = get_memory_summary()
print(f"Memory system ready, startup preview length={len(memory_context_preview)}")


class ChatRequest(BaseModel):
    message: str


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


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Text chat through Ombre Gateway."""
    try:
        prepared = prepare_chat_turn(request.message)

        response = claude_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=prepared.system_prompt,
            messages=[
                {"role": "user", "content": request.message}
            ]
        )

        reply_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                reply_text += block.text

        try:
            await consolidate_chat_turn(request.message, reply_text)
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
async def voice_chat(audio: UploadFile = File(...)):
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
        prepared = prepare_chat_turn(user_text)

        response = claude_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=prepared.system_prompt,
            messages=[
                {"role": "user", "content": user_text}
            ]
        )

        assistant_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                assistant_text += block.text

        audio_output_path = await text_to_speech(assistant_text)

        try:
            await consolidate_chat_turn(user_text, assistant_text)
        except Exception as mem_error:
            print(f"Memory consolidation failed: {mem_error}")

        return {
            "user_audio_url": f"/audio/input/{audio_filename}",
            "user_text": user_text,
            "assistant_text": assistant_text,
            "assistant_audio_url": f"/audio/output/{os.path.basename(audio_output_path)}"
        }

    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
