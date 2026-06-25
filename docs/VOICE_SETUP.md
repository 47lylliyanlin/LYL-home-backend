# ElevenLabs 语音配置说明

这份说明是给 Kiro 的“说话”功能用的。你不需要理解代码，只要把 ElevenLabs 的两个值填进 `.env`，后端就会用 ElevenLabs 生成语音。

## 1. 需要准备什么

你需要有：

- ElevenLabs 账号
- 一个 ElevenLabs API Key
- 一个 Voice ID，也就是你想让 Kiro 使用的声音

## 2. 创建 `.env`

在 `F:\kiro-project\backend` 目录里，复制 `.env.example`，改名为 `.env`。

然后至少填写这两行：

```env
ELEVENLABS_API_KEY=你的ElevenLabs API Key
ELEVENLABS_VOICE_ID=你的Voice ID
```

推荐完整配置是：

```env
ELEVENLABS_API_KEY=你的ElevenLabs API Key
ELEVENLABS_VOICE_ID=你的Voice ID
ELEVENLABS_MODEL_ID=eleven_multilingual_v2
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
ELEVENLABS_STABILITY=0.5
ELEVENLABS_SIMILARITY_BOOST=0.75
ELEVENLABS_STYLE=0.0
ELEVENLABS_USE_SPEAKER_BOOST=true
```

`.env` 已经被 `.gitignore` 忽略，不会上传到 GitHub。

## 3. 这些参数是什么意思

- `ELEVENLABS_API_KEY`：ElevenLabs 的钥匙，没有它不能调用服务。
- `ELEVENLABS_VOICE_ID`：声音 ID，决定 Kiro 用哪一种声音。
- `ELEVENLABS_MODEL_ID`：语音模型，中文建议先用 `eleven_multilingual_v2`。
- `ELEVENLABS_OUTPUT_FORMAT`：输出音频格式，默认生成 mp3。
- `ELEVENLABS_STABILITY`：声音稳定度，越高越稳定，越低越有情绪变化。
- `ELEVENLABS_SIMILARITY_BOOST`：声音相似度增强，一般保持 `0.75`。
- `ELEVENLABS_STYLE`：风格强度，先保持 `0.0`，后面想更有表现力再调高。
- `ELEVENLABS_USE_SPEAKER_BOOST`：增强说话人特征，建议 `true`。

## 4. 单独测试 Kiro 能不能说话

打开 PowerShell，运行：

```powershell
cd F:\kiro-project\backend
venv\Scripts\activate
python test_elevenlabs_tts.py
```

如果成功，会看到类似：

```text
[OK] ElevenLabs TTS generated: F:\kiro-project\backend\audio\output\tts_xxx.mp3
```

然后去 `F:\kiro-project\backend\audio\output` 里打开这个 mp3，听一下声音是否正常。

## 5. 和现有接口的关系

现有接口不用改：

- `/api/tts`：输入文字，直接返回 mp3。
- `/api/voice-chat`：你发语音给 Kiro，Kiro 识别后回复文字，并用 ElevenLabs 生成语音回复。

前端收到的字段仍然是：

```json
{
  "assistant_audio_url": "/audio/output/tts_xxx.mp3"
}
```

所以前端播放逻辑不用跟着改。

## 6. 常见错误

### Missing required environment variable: ELEVENLABS_API_KEY

说明 `.env` 里没有填 `ELEVENLABS_API_KEY`，或后端没有从 `F:\kiro-project\backend` 启动。

### Missing required environment variable: ELEVENLABS_VOICE_ID

说明 `.env` 里没有填声音 ID。

### ElevenLabs TTS failed: 401

通常是 API Key 不对，或者复制时多了空格。

### ElevenLabs TTS failed: 422

通常是 Voice ID、模型名或参数格式不对。先只保留 API Key、Voice ID、Model ID 三项测试。

## 7. 下一步可以优化什么

语音部分后面可以继续做：

- 给 Kiro 选择固定人格声音
- 增加“温柔 / 活泼 / 平静”等语音模式
- 前端增加语音设置面板
- 把 STT 里临时写死的 ffmpeg 路径改成可配置项
- 做流式语音，让 Kiro 更快开始说话