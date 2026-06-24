"""
TTS (Text-to-Speech) 模块
使用 Edge TTS 将文字转换为语音
"""

import edge_tts
import asyncio
import os
from datetime import datetime

# Edge TTS 中文语音选项
# 可以选择不同的声音
VOICE = "zh-CN-XiaoxiaoNeural"  # 晓晓 - 女声，温柔
# 其他选项：
# "zh-CN-YunxiNeural"  # 云希 - 男声
# "zh-CN-YunyangNeural"  # 云扬 - 男声，新闻播报风格
# "zh-CN-XiaoyiNeural"  # 晓伊 - 女声，亲切

OUTPUT_DIR = "audio/output"

async def text_to_speech_async(text: str, output_path: str = None) -> str:
    """
    将文字转换为语音（异步）

    Args:
        text: 要转换的文字
        output_path: 输出文件路径（可选）

    Returns:
        生成的音频文件路径
    """
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 如果没有指定输出路径，自动生成
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = os.path.join(OUTPUT_DIR, f"tts_{timestamp}.mp3")

    # 使用 Edge TTS 生成语音
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_path)

    return output_path

# 导出异步版本为主要函数
text_to_speech = text_to_speech_async
