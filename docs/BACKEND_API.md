# Kiro 后端API文档

> 详细说明后端接口的使用方法、参数、返回值

---

## 📡 API基础信息

**Base URL：** `http://localhost:8000`

**部署后URL：** `https://你的域名`（待部署）

**Content-Type：** `application/json`（文字接口）、`multipart/form-data`（文件上传）

**CORS：** 已启用，允许所有域名访问

---

## 🔌 接口列表

### 1. 健康检查

**接口：** `GET /`

**描述：** 检查后端服务是否在线

**请求示例：**
```bash
curl http://localhost:8000/
```

**响应示例：**
```json
{
  "message": "Hello, 我是Kiro的后端服务"
}
```

**状态码：**
- `200` - 服务正常

---

### 2. 语音对话

**接口：** `POST /api/voice-chat`

**描述：** 上传语音文件，返回AI的文字和语音回复

**请求参数：**

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| audio | File | ✅ | 音频文件（支持.wav/.mp3/.webm） |

**请求示例：**
```bash
curl -X POST http://localhost:8000/api/voice-chat \
  -F "audio=@recording.wav"
```

**JavaScript示例：**
```javascript
const formData = new FormData();
formData.append('audio', audioBlob, 'recording.wav');

const response = await fetch('http://localhost:8000/api/voice-chat', {
  method: 'POST',
  body: formData
});

const data = await response.json();
```

**响应示例：**
```json
{
  "user_audio_url": "/audio/input/recording_20260624_103045.wav",
  "user_text": "你好，今天天气怎么样？",
  "assistant_text": "今天天气不错呀，阳光明媚，适合出去走走～",
  "assistant_audio_url": "/audio/output/tts_20260624_103046.mp3"
}
```

**响应字段说明：**

| 字段 | 类型 | 描述 |
|------|------|------|
| user_audio_url | string | 用户音频的访问路径 |
| user_text | string | 语音识别结果（用户说的话） |
| assistant_text | string | AI回复的文字内容 |
| assistant_audio_url | string | AI语音回复的访问路径 |

**音频文件访问：**
- 用户音频：`http://localhost:8000/audio/input/recording_xxx.wav`
- AI音频：`http://localhost:8000/audio/output/tts_xxx.mp3`

**状态码：**
- `200` - 成功
- `400` - 请求参数错误
- `500` - 服务器内部错误

**错误响应示例：**
```json
{
  "error": "语音识别失败：音频文件格式不支持"
}
```

---

### 3. 文字对话

**接口：** `POST /api/chat`

**描述：** 发送文字消息，返回AI的文字回复（不生成语音）

**请求参数：**

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| message | string | ✅ | 用户输入的文字 |

**请求示例：**
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}'
```

**JavaScript示例：**
```javascript
const response = await fetch('http://localhost:8000/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: '你好' })
});

const data = await response.json();
```

**响应示例：**
```json
{
  "reply": "你好呀～有什么我可以帮你的吗？"
}
```

**响应字段说明：**

| 字段 | 类型 | 描述 |
|------|------|------|
| reply | string | AI的文字回复 |

**状态码：**
- `200` - 成功
- `400` - 请求参数错误
- `500` - 服务器内部错误

**错误响应示例：**
```json
{
  "error": "消息不能为空"
}
```

---

### 4. 静态文件访问

**音频文件目录：**

#### 用户音频
- **路径：** `/audio/input/{filename}`
- **示例：** `http://localhost:8000/audio/input/recording_20260624_103045.wav`

#### AI音频
- **路径：** `/audio/output/{filename}`
- **示例：** `http://localhost:8000/audio/output/tts_20260624_103046.mp3`

**支持的音频格式：**
- `.wav` - 用户录音
- `.mp3` - AI语音合成

---

## 🔄 完整对话流程

### 语音对话流程

```
用户
  ↓
1. 前端录音 → MediaRecorder → audioBlob
  ↓
2. 上传音频 → POST /api/voice-chat
  ↓
后端处理：
  ├─ 保存音频文件 → audio/input/
  ├─ 语音识别（STT） → FunASR
  ├─ 检索记忆 → ChromaDB
  ├─ AI生成回复 → Claude API
  └─ 语音合成（TTS） → MeloTTS → audio/output/
  ↓
3. 返回结果 → {user_text, assistant_text, audio_urls}
  ↓
4. 前端播放 → Audio API
```

### 文字对话流程

```
用户输入文字
  ↓
POST /api/chat → {message: "用户消息"}
  ↓
后端处理：
  ├─ 检索记忆 → ChromaDB
  └─ AI生成回复 → Claude API
  ↓
返回结果 → {reply: "AI回复"}
  ↓
前端显示
```

---

## 🧠 记忆系统说明

### 记忆存储

**位置：** `backend/memory/` 目录

**格式：** Markdown文件

**示例：** `backend/memory/user_info.md`
```markdown
---
name: user-basic-info
description: 用户的基本信息和喜好
metadata:
  type: user
---

用户叫小G，喜欢看动漫，养了一只猫叫咪咪。
```

### 记忆检索

**触发时机：** 每次对话前自动检索

**检索逻辑：**
1. 读取 `memory/` 目录下的所有 `.md` 文件
2. 将用户消息转换为向量
3. 在ChromaDB中搜索相似度最高的3条记忆
4. 将相关记忆加入Claude的系统提示词

**检索示例：**
```
用户输入："我的猫今天不吃饭"
  ↓
检索到记忆："用户养了一只猫叫咪咪"
  ↓
Claude收到的提示：
  系统：你是Kiro，用户养了一只猫叫咪咪
  用户：我的猫今天不吃饭
  ↓
Claude回复："咪咪今天怎么了呀？是不是不舒服？"
```

---

## ⚙️ 配置说明

### 环境变量（待实现）

创建 `.env` 文件：
```env
# Claude API
ANTHROPIC_API_KEY=your_api_key_here

# 服务器配置
HOST=0.0.0.0
PORT=8000

# 音频配置
MAX_AUDIO_SIZE=10MB
AUDIO_FORMATS=wav,mp3,webm

# 记忆系统
MEMORY_DIR=./memory
CHROMA_DB_DIR=./chroma_db
```

### 依赖安装

**requirements.txt：**
```
fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6
anthropic==0.7.0
funasr==1.0.0
modelscope==1.9.0
melo-tts==0.1.0
chromadb==0.4.18
```

**安装命令：**
```bash
pip install -r requirements.txt
```

---

## 🚀 启动服务

### 开发模式
```bash
cd backend
venv\Scripts\activate
python main.py
```

服务器地址：`http://localhost:8000`

### 生产模式（待实现）
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## 🐛 错误处理

### 常见错误码

| 状态码 | 错误类型 | 描述 | 解决方案 |
|--------|----------|------|----------|
| 400 | Bad Request | 请求参数错误 | 检查参数格式和必填项 |
| 404 | Not Found | 接口不存在 | 检查URL路径 |
| 413 | Payload Too Large | 音频文件过大 | 压缩音频或缩短录音时长 |
| 500 | Internal Server Error | 服务器内部错误 | 查看后端日志 |
| 503 | Service Unavailable | 服务不可用 | 检查后端是否启动 |

### 错误响应格式

```json
{
  "error": "错误描述信息",
  "detail": "详细错误堆栈（开发模式）"
}
```

---

## 📊 性能指标

### 响应时间（本地测试）

| 接口 | 平均响应时间 | 说明 |
|------|-------------|------|
| GET / | ~10ms | 健康检查 |
| POST /api/chat | ~2-3s | 文字对话 |
| POST /api/voice-chat | ~5-8s | 语音对话 |

**语音对话时间分解：**
- 上传音频：~100ms
- 语音识别：~1-2s
- 记忆检索：~50ms
- Claude生成：~2-3s
- 语音合成：~1-2s

### 资源占用

- **内存：** ~2GB（包含模型）
- **CPU：** 识别/合成时占用较高
- **磁盘：** ~3GB（模型文件）

---

## 🔐 安全建议（待实现）

### API认证
```python
from fastapi import Header, HTTPException

async def verify_token(authorization: str = Header(...)):
    if authorization != f"Bearer {SECRET_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
```

### 请求限制
```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/chat")
@limiter.limit("10/minute")  # 每分钟最多10次请求
async def chat(request: dict):
    ...
```

### 文件大小限制
```python
from fastapi import UploadFile, HTTPException

@app.post("/api/voice-chat")
async def voice_chat(audio: UploadFile = File(...)):
    if audio.size > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=413, detail="文件过大")
```

---

## 📝 API测试

### 使用Postman测试

#### 测试语音对话
1. 新建POST请求：`http://localhost:8000/api/voice-chat`
2. Body选择 `form-data`
3. 添加字段：`audio` (File类型)
4. 选择音频文件
5. 点击Send

#### 测试文字对话
1. 新建POST请求：`http://localhost:8000/api/chat`
2. Body选择 `raw` → `JSON`
3. 输入：`{"message": "你好"}`
4. 点击Send

---

## 🔄 版本历史

### v1.0.0 (2026-06-24)
- ✅ 语音识别接口
- ✅ 语音合成接口
- ✅ 文字对话接口
- ✅ 记忆系统集成
- ✅ 静态文件服务

### 计划中 (v1.1.0)
- [ ] 用户认证系统
- [ ] 对话历史保存到数据库
- [ ] 流式TTS（边生成边播放）
- [ ] WebSocket实时通信
- [ ] API限流和缓存

---

## 📞 技术支持

**GitHub仓库：** https://github.com/47lylliyanlin/LYL-home-backend

**问题反馈：** 在GitHub Issues提交

**文档更新：** 2026年6月24日

---

## 附录：Claude API集成

### Claude提示词模板

```python
system_prompt = """
你是Kiro，一个温暖的AI助手。

相关记忆：
{memories}

请根据记忆和用户消息，给出自然、温暖的回复。
"""

user_message = f"{user_text}"

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=system_prompt.format(memories=memories),
    messages=[{"role": "user", "content": user_message}]
)
```

### 记忆格式

```python
memories = [
    "用户叫小G，喜欢看动漫",
    "用户养了一只猫叫咪咪",
    "用户在学习编程"
]

# 拼接成提示词
memories_text = "\n".join(f"- {m}" for m in memories)
```

---

**本文档持续更新中...**
