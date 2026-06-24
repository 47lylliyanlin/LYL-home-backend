import whisper
import os

# 设置ffmpeg路径
os.environ["PATH"] = r"C:\ffmpeg\ffmpeg-8.1.1-essentials_build\bin" + os.pathsep + os.environ.get("PATH", "")

# 加载Whisper模型（small模型，平衡速度和准确度）
model = whisper.load_model("small")

def transcribe_audio(audio_path: str) -> str:
    """
    将音频文件转换为文字

    Args:
        audio_path: 音频文件路径

    Returns:
        识别出的文字
    """
    try:
        result = model.transcribe(audio_path, language="zh")
        return result["text"]
    except Exception as e:
        raise Exception(f"语音识别失败: {str(e)}")
