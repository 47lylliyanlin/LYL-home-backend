"""
整合F:/our_memories到记忆系统
将宝宝写的记忆导入到Ombre-Brain记忆系统
"""

import os
import yaml
from pathlib import Path
from datetime import datetime
from api.memory import memory_system

OUR_MEMORIES_DIR = "F:/our_memories"

def parse_our_memory(file_path: Path):
    """解析our_memories中的记忆文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析frontmatter
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            metadata = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
            return metadata, body

    return {}, content

def import_our_memories():
    """导入F:/our_memories中的所有记忆"""
    print("开始导入our_memories...")

    our_memories_path = Path(OUR_MEMORIES_DIR)
    if not our_memories_path.exists():
        print(f"目录不存在: {OUR_MEMORIES_DIR}")
        return

    imported_count = 0

    for file_path in our_memories_path.glob("*.md"):
        # 跳过索引文件和README
        if file_path.name in ['MEMORY.md', 'README.md']:
            continue

        try:
            metadata, content = parse_our_memory(file_path)

            # 判断记忆类型
            mem_type_map = {
                'user': 'permanent',
                'reference': 'permanent',
                'project': 'dynamic',
                'feedback': 'permanent',
                'feel': 'feel'
            }

            original_type = metadata.get('metadata', {}).get('type', metadata.get('type', 'user'))
            mem_type = mem_type_map.get(original_type, 'permanent')

            # 评估重要度
            importance = 10 if mem_type == 'permanent' else 7

            # 提取标签
            name = metadata.get('name', file_path.stem)
            tags = [name, original_type]

            # 创建记忆
            memory = memory_system.create_memory(
                content=content,
                importance=importance,
                mem_type=mem_type,
                tags=tags,
                valence=0.6,  # 默认中性偏正面
                arousal=0.5   # 默认中等唤醒度
            )

            print(f"[OK] 导入: {file_path.name} -> {memory.id} ({mem_type})")
            imported_count += 1

        except Exception as e:
            print(f"[ERROR] 导入失败 {file_path.name}: {e}")

    print(f"\n导入完成！共 {imported_count} 条记忆")

if __name__ == "__main__":
    import_our_memories()
