"""
Kiro记忆系统 - 基于Ombre-Brain设计
支持动态记忆、衰减、自动归档
"""

import os
import yaml
import chromadb
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# 配置
MEMORY_DIR = "./memory"
CHROMA_DIR = "./chroma_db"

# 初始化ChromaDB
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
memory_collection = chroma_client.get_or_create_collection(
    name="kiro_memories",
    metadata={"hnsw:space": "cosine"}
)

class Memory:
    """单条记忆"""
    def __init__(self, file_path: str, metadata: Dict, content: str):
        self.file_path = file_path
        self.id = metadata.get('id', self._generate_id())
        self.importance = metadata.get('importance', 5)
        self.valence = metadata.get('valence', 0.5)
        self.arousal = metadata.get('arousal', 0.5)
        self.tags = metadata.get('tags', [])
        self.created = self._parse_datetime(metadata.get('created'))
        self.last_used = self._parse_datetime(metadata.get('last_used', metadata.get('created')))
        self.use_count = metadata.get('use_count', 0)
        self.type = metadata.get('type', 'dynamic')
        self.content = content

    def _generate_id(self) -> str:
        """生成唯一ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"mem_{timestamp}"

    def _parse_datetime(self, dt_str: Any) -> datetime:
        """解析时间字符串"""
        if isinstance(dt_str, datetime):
            return dt_str
        if isinstance(dt_str, str):
            try:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            except:
                pass
        return datetime.now()

    def calculate_score(self) -> float:
        """
        计算记忆分数（用于排序）
        score = importance × decay_factor × activation_bonus
        """
        # permanent类型不衰减
        if self.type == 'permanent':
            return self.importance * 10

        # 计算时间衰减
        days_since_last_used = (datetime.now() - self.last_used).days
        decay_factor = 1 / (1 + days_since_last_used * 0.05)

        # 使用次数加成
        activation_bonus = 1 + (self.use_count * 0.1)

        score = self.importance * decay_factor * activation_bonus
        return score

    def mark_used(self):
        """标记记忆被使用"""
        self.last_used = datetime.now()
        self.use_count += 1

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'importance': self.importance,
            'valence': self.valence,
            'arousal': self.arousal,
            'tags': self.tags,
            'created': self.created.isoformat(),
            'last_used': self.last_used.isoformat(),
            'use_count': self.use_count,
            'type': self.type,
            'content': self.content,
            'score': self.calculate_score()
        }

    def to_yaml_frontmatter(self) -> str:
        """生成YAML frontmatter"""
        return f"""---
id: {self.id}
importance: {self.importance}
valence: {self.valence}
arousal: {self.arousal}
tags: {self.tags}
created: {self.created.isoformat()}
last_used: {self.last_used.isoformat()}
use_count: {self.use_count}
type: {self.type}
---

{self.content}
"""

class MemorySystem:
    """记忆系统"""

    def __init__(self):
        self.memory_dir = Path(MEMORY_DIR)
        self._ensure_directories()

    def _ensure_directories(self):
        """确保目录存在"""
        (self.memory_dir / "permanent").mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "dynamic").mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "feel").mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "archive").mkdir(parents=True, exist_ok=True)

    def load_memory_file(self, file_path: Path) -> Optional[Memory]:
        """加载单个记忆文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 解析YAML frontmatter
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                    return Memory(str(file_path), metadata, body)

            # 没有frontmatter，创建默认元数据
            metadata = {'type': file_path.parent.name}
            return Memory(str(file_path), metadata, content.strip())

        except Exception as e:
            print(f"读取记忆文件失败 {file_path}: {e}")
            return None

    def load_all_memories(self, include_archive: bool = False) -> List[Memory]:
        """
        加载所有记忆

        Args:
            include_archive: 是否包含归档记忆
        """
        memories = []

        # 扫描目录
        dirs = ['permanent', 'dynamic', 'feel']
        if include_archive:
            dirs.append('archive')

        for dir_name in dirs:
            dir_path = self.memory_dir / dir_name
            if dir_path.exists():
                for file_path in dir_path.glob("*.md"):
                    memory = self.load_memory_file(file_path)
                    if memory:
                        memories.append(memory)

        return memories

    def search_memories(self, query: str, top_k: int = 5) -> List[Memory]:
        """
        检索记忆（向量搜索 + 衰减分排序）

        Args:
            query: 查询文本
            top_k: 返回数量
        """
        # 1. 向量搜索
        try:
            results = memory_collection.query(
                query_texts=[query],
                n_results=top_k * 2  # 多取一些，后面再排序
            )

            if not results['ids'] or not results['ids'][0]:
                return []

            memory_ids = results['ids'][0]
        except Exception as e:
            print(f"向量搜索失败: {e}")
            memory_ids = []

        # 2. 加载完整记忆
        all_memories = self.load_all_memories()
        id_to_memory = {m.id: m for m in all_memories}

        found_memories = []
        for mem_id in memory_ids:
            if mem_id in id_to_memory:
                found_memories.append(id_to_memory[mem_id])

        # 如果向量搜索没结果，返回所有记忆
        if not found_memories:
            found_memories = all_memories

        # 3. 按分数排序
        found_memories.sort(key=lambda m: m.calculate_score(), reverse=True)

        # 4. 标记使用
        for memory in found_memories[:top_k]:
            memory.mark_used()
            self.save_memory(memory)

        return found_memories[:top_k]

    def save_memory(self, memory: Memory) -> bool:
        """
        保存记忆到文件

        Args:
            memory: Memory对象
        """
        try:
            # 确定保存路径
            if memory.file_path:
                file_path = Path(memory.file_path)
            else:
                # 新记忆，根据type决定目录
                dir_name = memory.type
                file_path = self.memory_dir / dir_name / f"{memory.id}.md"

            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(memory.to_yaml_frontmatter())

            # 更新向量数据库
            try:
                memory_collection.upsert(
                    ids=[memory.id],
                    documents=[memory.content],
                    metadatas=[{
                        'importance': memory.importance,
                        'type': memory.type,
                        'tags': ','.join(memory.tags)
                    }]
                )
            except Exception as e:
                print(f"更新向量数据库失败: {e}")

            return True

        except Exception as e:
            print(f"保存记忆失败: {e}")
            return False

    def create_memory(
        self,
        content: str,
        importance: int = 5,
        mem_type: str = "dynamic",
        tags: List[str] = None,
        valence: float = 0.5,
        arousal: float = 0.5
    ) -> Memory:
        """
        创建新记忆

        Args:
            content: 记忆内容
            importance: 重要度 1-10
            mem_type: 类型 permanent/dynamic/feel
            tags: 标签列表
            valence: 情感效价 0-1
            arousal: 情感唤醒度 0-1
        """
        metadata = {
            'importance': importance,
            'type': mem_type,
            'tags': tags or [],
            'valence': valence,
            'arousal': arousal,
            'created': datetime.now().isoformat(),
            'last_used': datetime.now().isoformat(),
            'use_count': 0
        }

        memory = Memory(None, metadata, content)
        self.save_memory(memory)

        return memory

    def archive_old_memories(self, score_threshold: float = 2.0):
        """
        归档低分记忆

        Args:
            score_threshold: 分数阈值，低于此值的dynamic记忆会被归档
        """
        memories = self.load_all_memories()

        for memory in memories:
            # 只归档dynamic类型
            if memory.type != 'dynamic':
                continue

            # 分数低于阈值
            if memory.calculate_score() < score_threshold:
                # 移动到archive目录
                old_path = Path(memory.file_path)
                new_path = self.memory_dir / "archive" / old_path.name

                try:
                    old_path.rename(new_path)
                    memory.file_path = str(new_path)
                    memory.type = 'archive'
                    print(f"归档记忆: {memory.id}")
                except Exception as e:
                    print(f"归档失败 {memory.id}: {e}")

    def format_memories_for_claude(self, memories: List[Memory]) -> str:
        """格式化记忆为Claude可读文本"""
        if not memories:
            return "（暂无相关记忆）"

        text = "# 我的记忆\n\n"

        for memory in memories:
            # 显示标签
            tags_str = ', '.join(memory.tags) if memory.tags else ''

            text += f"## {memory.id}\n"
            if tags_str:
                text += f"*标签: {tags_str}*\n\n"

            text += f"{memory.content}\n\n"

            # 显示情感坐标（调试用）
            # text += f"*[重要度:{memory.importance} 效价:{memory.valence} 唤醒:{memory.arousal}]*\n\n"

            text += "---\n\n"

        return text

# 全局实例
memory_system = MemorySystem()

# 兼容旧接口
def get_memory_summary() -> str:
    """获取记忆摘要（兼容旧代码）"""
    memories = memory_system.load_all_memories()
    # 按分数排序，取前5条
    memories.sort(key=lambda m: m.calculate_score(), reverse=True)
    return memory_system.format_memories_for_claude(memories[:5])
