"""
记忆系统模块
从 F:/our_memories/ 读取所有记忆文件，格式化后提供给Claude
"""

import os
import yaml
from pathlib import Path
from typing import List, Dict, Any

MEMORY_DIR = "F:/our_memories"

def load_all_memories() -> List[Dict[str, Any]]:
    """
    加载所有记忆文件

    Returns:
        记忆列表，每个记忆包含 metadata 和 content
    """
    memories = []

    if not os.path.exists(MEMORY_DIR):
        print(f"警告：记忆目录不存在 {MEMORY_DIR}")
        return memories

    # 遍历所有 .md 文件
    for file_path in Path(MEMORY_DIR).rglob("*.md"):
        try:
            memory = load_memory_file(str(file_path))
            if memory:
                memories.append(memory)
        except Exception as e:
            print(f"读取记忆文件失败 {file_path}: {e}")

    return memories

def load_memory_file(file_path: str) -> Dict[str, Any]:
    """
    读取单个记忆文件

    Args:
        file_path: 文件路径

    Returns:
        包含 metadata 和 content 的字典
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 分离 YAML frontmatter 和正文
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1])
                body = parts[2].strip()
                return {
                    "metadata": metadata,
                    "content": body,
                    "file_path": file_path
                }
            except yaml.YAMLError as e:
                print(f"YAML解析失败 {file_path}: {e}")

    # 如果没有 frontmatter，整个内容作为 content
    return {
        "metadata": {},
        "content": content.strip(),
        "file_path": file_path
    }

def format_memories_for_claude(memories: List[Dict[str, Any]]) -> str:
    """
    格式化记忆为适合Claude的文本

    Args:
        memories: 记忆列表

    Returns:
        格式化后的记忆文本
    """
    if not memories:
        return "（暂无记忆）"

    # 按类型和重要性排序
    def sort_key(mem):
        meta = mem.get('metadata', {})
        # project/feedback 类型优先
        type_priority = {'project': 0, 'feedback': 1, 'user': 2, 'reference': 3}
        mem_type = meta.get('metadata', {}).get('type', 'user')
        priority = type_priority.get(mem_type, 99)
        return priority

    memories.sort(key=sort_key)

    # 拼接成文本
    text = "# 我的记忆\n\n"

    for mem in memories:
        meta = mem.get('metadata', {})
        content = mem.get('content', '')

        # 标题
        name = meta.get('name', '未命名记忆')
        description = meta.get('description', '')

        text += f"## {name}\n"
        if description:
            text += f"> {description}\n\n"

        text += f"{content}\n\n"
        text += "---\n\n"

    return text

def get_memory_summary() -> str:
    """
    获取记忆摘要（用于系统提示）

    Returns:
        记忆摘要文本
    """
    memories = load_all_memories()
    return format_memories_for_claude(memories)
