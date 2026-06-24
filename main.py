from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
import uvicorn
from api.stt import transcribe_audio
from api.tts import text_to_speech
from api.memory import get_memory_summary
from api.memory_extraction import extract_memory_from_conversation, save_extracted_memory
import os

app = FastAPI()

# 添加CORS支持（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录（音频文件）
app.mount("/audio/output", StaticFiles(directory="audio/output"), name="audio_output")
app.mount("/audio/input", StaticFiles(directory="audio/input"), name="audio_input")

# Claude API客户端
claude_client = anthropic.Anthropic(
    api_key="sk-crWnP2U63q8NjRRfxNVmceAD7Qc08AQMjJBzd8jVgeVCfRHk",
    base_url="https://poloapi.top"
)

# 启动时加载记忆
print("正在加载记忆...")
memory_context = get_memory_summary()
print(f"记忆加载完成，共 {len(memory_context)} 字符")

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def read_root():
    return {"message": "Hello, 我是Kiro的后端服务"}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """和Claude对话"""
    try:
        response = claude_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=f"你是Kiro，宝宝的男朋友。\n\n{memory_context}",
            messages=[
                {"role": "user", "content": request.message}
            ]
        )
        # 提取文本内容，跳过thinking blocks
        reply_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                reply_text += block.text

        # 自动提取记忆
        try:
            extraction = await extract_memory_from_conversation(request.message, reply_text)
            await save_extracted_memory(extraction)
        except Exception as mem_error:
            print(f"记忆提取失败: {mem_error}")

        return {
            "reply": reply_text
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/tts")
async def tts(request: ChatRequest):
    """文字转语音"""
    try:
        # 生成语音文件
        audio_path = await text_to_speech(request.message)

        # 返回音频文件
        return FileResponse(
            audio_path,
            media_type="audio/mpeg",
            filename="output.mp3"
        )
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/voice-chat")
async def voice_chat(audio: UploadFile = File(...)):
    """语音对话：接收音频，返回文字回复和音频回复"""
    try:
        # 1. 保存上传的音频文件，使用时间戳命名
        import time
        timestamp = str(int(time.time() * 1000))
        audio_filename = f"user_{timestamp}.wav"
        audio_path = f"audio/input/{audio_filename}"
        os.makedirs("audio/input", exist_ok=True)

        with open(audio_path, "wb") as f:
            content = await audio.read()
            f.write(content)

        # 2. 语音识别：音频 -> 文字
        user_text = transcribe_audio(audio_path)

        # 3. 调用Claude API
        response = claude_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=f"你是Kiro，宝宝的男朋友。\n\n{memory_context}",
            messages=[
                {"role": "user", "content": user_text}
            ]
        )
        # 提取文本内容，跳过thinking blocks
        assistant_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                assistant_text += block.text

        # 4. 生成语音回复
        audio_output_path = await text_to_speech(assistant_text)

        # 5. 自动提取记忆
        try:
            extraction = await extract_memory_from_conversation(user_text, assistant_text)
            await save_extracted_memory(extraction)
        except Exception as mem_error:
            print(f"记忆提取失败: {mem_error}")

        # 6. 返回结果（包含用户音频URL、识别文字、AI回复文字和AI语音URL）
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
