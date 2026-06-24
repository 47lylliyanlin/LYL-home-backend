"""
自动提取对话记忆
"""

import anthropic
import os
from datetime import datetime
from typing import Dict, List, Optional
from .memory import memory_system

# Claude API客户端
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

async def extract_memory_from_conversation(
    user_message: str,
    assistant_message: str,
    conversation_history: List[Dict] = None
) -> Optional[Dict]:
    """
    从对话中提取需要记住的信息

    Returns:
        {
            'should_remember': bool,
            'content': str,
            'importance': int,
            'valence': float,
            'arousal': float,
            'tags': List[str],
            'type': str  # 'permanent', 'dynamic', 'feel'
        }
    """

    # 构建判断提示词
    prompt = f"""分析这段对话，判断是否有需要长期记住的信息。

用户说: {user_message}
我回复: {assistant_message}

需要记住的信息类型：
1. permanent - 用户的基本信息、重要喜好、关系中的重要事实
2. dynamic - 临时话题、近期计划、对话内容
3. feel - 我对这次对话的感受、情绪体验

判断标准：
- 用户分享了关于自己的重要信息
- 对话中有情感上的重要瞬间
- 用户表达了需求、期望、失落
- 我们之间发生了有意义的交流

返回JSON格式：
{{
    "should_remember": true/false,
    "content": "简洁的记忆内容（1-3句话）",
    "importance": 1-10,
    "valence": 0.0-1.0,
    "arousal": 0.0-1.0,
    "tags": ["标签1", "标签2"],
    "type": "permanent/dynamic/feel",
    "reason": "为什么要记住这个"
}}

如果不需要记住，返回 {{"should_remember": false}}
"""

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        import json
        result = json.loads(response.content[0].text)
        return result

    except Exception as e:
        print(f"提取记忆失败: {e}")
        return None


async def save_extracted_memory(extraction: Dict):
    """保存提取的记忆"""
    if not extraction or not extraction.get('should_remember'):
        return

    memory = memory_system.create_memory(
        content=extraction['content'],
        importance=extraction.get('importance', 5),
        mem_type=extraction.get('type', 'dynamic'),
        tags=extraction.get('tags', []),
        valence=extraction.get('valence', 0.5),
        arousal=extraction.get('arousal', 0.5)
    )

    print(f"保存记忆: {memory.id} - {extraction['content'][:50]}...")
    return memory
