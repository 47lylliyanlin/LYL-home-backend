# Kiro 开发日志

> 记录每个功能的详细实现步骤、使用的技术和遇到的问题

---

## 📅 2026年6月24日 - 项目启动

### 1. 环境搭建

#### 后端环境
```bash
# 创建项目目录
mkdir kiro-project
cd kiro-project
mkdir backend frontend

# 创建Python虚拟环境
cd backend
python -m venv venv
venv\Scripts\activate

# 安装基础依赖
pip install fastapi uvicorn python-multipart anthropic
```

**技术选择：**
- **FastAPI** - 现代化的Python Web框架，自动生成API文档，支持异步
- **uvicorn** - ASGI服务器，运行FastAPI应用
- **python-multipart** - 处理文件上传（音频文件）
- **anthropic** - Claude API的官方SDK

---

### 2. 语音识别（STT）实现

#### 安装FunASR
```bash
pip install funasr modelscope
```

#### 代码实现 - `api/stt.py`
```python
from funasr import AutoModel

# 初始化模型（阿里达摩院的语音识别模型）
model = AutoModel(
    model="paraformer-zh",  # 中文识别模型
    device="cpu"
)

async def speech_to_text(audio_path: str) -> str:
    result = model.generate(input=audio_path)
    return result[0]["text"]
```

**为什么选FunASR：**
- ✅ 本地运行，不需要调用外部API
- ✅ 中文识别准确率高
- ✅ 免费开源
- ❌ 模型较大（约1GB）

**遇到的问题：**
- 问题：首次加载模型很慢（30秒）
- 解决：启动时预加载模型，后续识别很快

---

### 3. 语音合成（TTS）实现

#### 安装MeloTTS
```bash
pip install melo-tts
```

#### 代码实现 - `api/tts.py`
```python
from melo.api import TTS

# 初始化TTS模型
tts_model = TTS(language='ZH', device='cpu')
speaker_id = tts_model.hps.data.spk2id['ZH']

async def text_to_speech(text: str) -> str:
    output_path = f"audio/output/tts_{timestamp}.mp3"
    tts_model.tts_to_file(
        text=text,
        speaker_id=speaker_id,
        output_path=output_path,
        speed=1.0
    )
    return output_path
```

**为什么选MeloTTS：**
- ✅ 本地运行，免费
- ✅ 中文语音自然
- ✅ 支持多种语音风格
- ❌ 生成速度较慢（3秒文本约需1秒）

---

### 4. 向量记忆系统实现

#### 安装ChromaDB
```bash
pip install chromadb
```

#### 代码实现 - `api/memory.py`
```python
import chromadb

# 初始化ChromaDB客户端
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="memories")

# 添加记忆
def add_memory(text: str, metadata: dict):
    collection.add(
        documents=[text],
        metadatas=[metadata],
        ids=[f"mem_{timestamp}"]
    )

# 检索记忆
def search_memory(query: str, top_k: int = 3):
    results = collection.query(
        query_texts=[query],
        n_results=top_k
    )
    return results['documents'][0]
```

**记忆系统工作原理：**
1. 用户输入 → 转换为向量（embedding）
2. 在向量数据库中搜索相似记忆
3. 把相关记忆加入到Claude的提示词中
4. Claude根据记忆生成回复

**ChromaDB的优势：**
- ✅ 本地运行，数据安全
- ✅ 自动生成embedding向量
- ✅ 支持相似度搜索
- ✅ 轻量级，适合小项目

---

### 5. FastAPI后端接口

#### 主文件 - `main.py`
```python
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# 跨域配置（允许前端访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# 静态文件服务（音频文件）
app.mount("/audio", StaticFiles(directory="audio"), name="audio")
```

**API接口列表：**

#### 1️⃣ 语音对话接口
```python
@app.post("/api/voice-chat")
async def voice_chat(audio: UploadFile = File(...)):
    # 1. 保存用户音频
    audio_path = save_audio(audio)
    
    # 2. 语音识别（STT）
    user_text = await speech_to_text(audio_path)
    
    # 3. 检索相关记忆
    memories = search_memory(user_text)
    
    # 4. 调用Claude生成回复
    assistant_text = await get_claude_response(user_text, memories)
    
    # 5. 语音合成（TTS）
    audio_url = await text_to_speech(assistant_text)
    
    return {
        "user_text": user_text,
        "assistant_text": assistant_text,
        "user_audio_url": f"/audio/input/{filename}",
        "assistant_audio_url": f"/audio/output/{filename}"
    }
```

#### 2️⃣ 文字对话接口
```python
@app.post("/api/chat")
async def chat(request: dict):
    user_message = request["message"]
    
    # 检索记忆 + Claude回复
    memories = search_memory(user_message)
    reply = await get_claude_response(user_message, memories)
    
    return {"reply": reply}
```

#### 3️⃣ 健康检查接口
```python
@app.get("/")
async def root():
    return {"message": "Hello, 我是Kiro的后端服务"}
```

---

### 6. 前端实现

#### HTML结构 - `frontend/index.html`

**核心功能模块：**

1. **录音功能**
```javascript
// 使用浏览器MediaRecorder API
navigator.mediaDevices.getUserMedia({ audio: true })
  .then(stream => {
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.start();
  });
```

2. **播放控制条**
```javascript
// 波形进度条（20个竖条）
for (let i = 0; i < 20; i++) {
  const bar = document.createElement('div');
  bar.className = 'wave-bar';
  bar.style.height = Math.random() * 12 + 8 + 'px';
}

// 播放时更新进度
audio.ontimeupdate = () => {
  const progress = audio.currentTime / audio.duration;
  const activeCount = Math.floor(progress * 20);
  // 激活对应数量的波形条
};
```

3. **聊天记录保存**
```javascript
// 使用localStorage保存
function saveChatHistory() {
  const messages = [...]; // 提取所有消息
  localStorage.setItem('kiro_chat_history', JSON.stringify(messages));
}

// 页面加载时恢复
function loadChatHistory() {
  const saved = localStorage.getItem('kiro_chat_history');
  if (saved) {
    const messages = JSON.parse(saved);
    messages.forEach(msg => addMessage(...));
  }
}
```

4. **加载动画**
```javascript
// 显示加载气泡（三个点）
function addLoadingMessage() {
  const typingBubble = document.createElement('div');
  typingBubble.className = 'typing';
  typingBubble.innerHTML = '<div class="td"></div><div class="td"></div><div class="td"></div>';
  // CSS动画让三个点跳动
}
```

---

### 7. UI优化细节

#### 播放条样式
```css
/* 用户播放条 - 粉色主题 */
.user-play-bar {
  background: #FAECE7;
  border: 1px solid #F5C4B3;
}

/* AI播放条 - 白色主题 */
.play-bar {
  background: #FFFFFF;
  border: 1px solid #F5C4B3;
}

/* 波形条动画 */
.wave-bar {
  background: #F5C4B3;
  transition: all 0.1s;
}

.wave-bar.active {
  background: #D85A30; /* 播放时变橙色 */
}
```

#### 加载动画
```css
.typing { display: flex; gap: 4px; }
.td { width: 6px; height: 6px; border-radius: 50%; background: #D85A30; }

@keyframes blink {
  0%, 80%, 100% { opacity: 0.2; }
  40% { opacity: 1; }
}

.td { animation: blink 1.3s infinite; }
.td:nth-child(2) { animation-delay: 0.2s; }
.td:nth-child(3) { animation-delay: 0.4s; }
```

---

### 8. Git版本管理

#### 初始化Git仓库
```bash
# 前端仓库
cd frontend
git init
git add .
git commit -m "Initial commit: Kiro frontend"
git remote add origin https://github.com/47lylliyanlin/LYL-home-frontend.git
git branch -M main
git push -u origin main

# 后端仓库
cd backend
git init

# 配置.gitignore（忽略不需要上传的文件）
echo "venv/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "audio/input/*" >> .gitignore
echo "audio/output/*" >> .gitignore
echo "chroma_db/" >> .gitignore

# 生成依赖列表
pip freeze > requirements.txt

git add .
git commit -m "Initial commit: Kiro backend"
git remote add origin https://github.com/47lylliyanlin/LYL-home-backend.git
git branch -M main
git push -u origin main
```

---

## 🐛 遇到的问题和解决方案

### 问题1：音频文件无法播放
**现象：** 前端显示"The element has no supported sources"

**原因：** 后端返回的音频路径不正确
- 返回：`/audio/tts_xxx.mp3`
- 实际路径：`/audio/output/tts_xxx.mp3`

**解决：**
```python
# 修改前
return {"assistant_audio_url": f"/audio/{os.path.basename(audio_path)}"}

# 修改后
return {"assistant_audio_url": f"/audio/output/{os.path.basename(audio_path)}"}
```

---

### 问题2：刷新页面后聊天记录丢失
**原因：** 没有持久化存储

**解决：** 使用localStorage保存聊天记录
- 优点：简单、免费、无需服务器
- 缺点：只能在同一浏览器访问，清空缓存就没了

---

### 问题3：用户语音气泡显示空白框
**原因：** 创建了空的bubble元素但没有内容

**解决：** 移除空的bubble，直接显示播放条
```javascript
// 修改前
const bubble = document.createElement('div');
bubble.className = 'bubble user-b';
bubble.textContent = ''; // 空内容
bwrap.appendChild(bubble);
bwrap.appendChild(playBar);

// 修改后
bwrap.appendChild(playBar); // 直接添加播放条
```

---

### 问题4：消息发送后没有反应
**原因：** loadChatHistory()在函数定义之前调用

**解决：** 将loadChatHistory()调用移到所有函数定义之后（文件末尾）

---

## 📊 技术架构图

```
用户
  ↓
前端（HTML/JS）
  ├─ 录音 → MediaRecorder API
  ├─ 播放 → Audio API
  └─ 存储 → localStorage
  ↓
后端（FastAPI）
  ├─ 语音识别 → FunASR
  ├─ 对话生成 → Claude API
  ├─ 记忆检索 → ChromaDB
  └─ 语音合成 → MeloTTS
  ↓
外部服务
  └─ Anthropic Claude API
```

---

## 📦 项目文件结构

```
kiro-project/
├── frontend/
│   └── index.html          # 前端页面（包含HTML/CSS/JS）
│
├── backend/
│   ├── main.py            # FastAPI主程序
│   ├── api/
│   │   ├── stt.py         # 语音识别
│   │   ├── tts.py         # 语音合成
│   │   └── memory.py      # 记忆系统
│   ├── audio/
│   │   ├── input/         # 用户音频
│   │   └── output/        # AI音频
│   ├── memory/            # 预设记忆文件
│   ├── chroma_db/         # 向量数据库
│   ├── venv/              # Python虚拟环境
│   ├── requirements.txt   # 依赖列表
│   └── .gitignore
│
├── PROJECT_PLAN.md        # 项目计划
├── DEVELOPMENT_LOG.md     # 开发日志（本文件）
└── BACKEND_API.md         # 后端API文档
```

---

## 🔧 本地运行步骤

### 1. 启动后端
```bash
cd backend
venv\Scripts\activate
python main.py
```
访问：http://localhost:8000

### 2. 启动前端
```bash
cd backend
python -m http.server 8080 --directory ../frontend
```
访问：http://localhost:8080

---

## 📝 待优化事项

### 高优先级
1. [ ] 云服务器部署
2. [ ] 对话自动保存到记忆系统
3. [ ] 完善错误处理

### 中优先级
4. [ ] 清空聊天记录按钮
5. [ ] 语音消息长按显示识别文字
6. [ ] 多轮对话上下文管理

### 低优先级
7. [ ] 用户认证系统
8. [ ] 性能优化（流式TTS）
9. [ ] 移动端适配

---

**最后更新：** 2026年6月24日
