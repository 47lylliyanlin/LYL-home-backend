"""
Kiro???? - ??Ombre-Brain??
????????????????????????
"""

import math
import os
import re
import yaml
import chromadb
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from .bucket_format import direct_seed_text

# ??
MEMORY_DIR = "./memory"
CHROMA_DIR = "./chroma_db"

STOP_TOKEN_CODES = {
    0x6211, 0x4f60, 0x4ed6, 0x5979, 0x5b83, 0x4eec, 0x7684, 0x4e86,
    0x662f, 0x5728, 0x6709, 0x548c, 0x5417, 0x5462, 0x554a, 0x5440,
    0x5427, 0x4e48, 0x4ec0, 0x8fd9, 0x90a3, 0x5c31, 0x90fd, 0x8fd8,
    0x8981, 0x4f1a, 0x80fd, 0x4e0d, 0x5f88, 0x4e5f, 0x53c8, 0x7ed9,
    0x8bf4, 0x95ee, 0x521a, 0x624d, 0x4e0a, 0x4e00, 0x53e5, 0x524d,
    0x540e, 0x91cc, 0x5230, 0x53bb, 0x6765, 0x505a, 0x770b, 0x60f3,
    0x77e5, 0x9053, 0x8bb0, 0x5f97, 0x8c01, 0x54ea, 0x4e2a, 0x4e3a,
    0x628a, 0x88ab, 0x4e0e, 0x6216,
}
STOP_TOKENS = {chr(code) for code in STOP_TOKEN_CODES}


# ???ChromaDB
chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
memory_collection = chroma_client.get_or_create_collection(
    name="kiro_memories",
    metadata={"hnsw:space": "cosine"}
)


def _env_float(name: str, default: float, min_value: float, max_value: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(max(value, min_value), max_value)


class Memory:
    """????"""

    def __init__(self, file_path: Optional[str], metadata: Dict, content: str):
        self.file_path = file_path
        self.id = metadata.get('id', self._generate_id())
        self.name = metadata.get('name', self.id)
        self.domain = metadata.get('domain', '')
        self.importance = int(metadata.get('importance', 5))
        self.valence = float(metadata.get('valence', 0.5))
        self.arousal = float(metadata.get('arousal', 0.5))
        self.tags = metadata.get('tags', []) or []
        self.created = self._parse_datetime(metadata.get('created'))
        self.last_used = self._parse_datetime(metadata.get('last_used', metadata.get('created')))
        self.last_active = self._parse_datetime(metadata.get('last_active', metadata.get('last_used', metadata.get('created'))))
        self.use_count = int(metadata.get('use_count', 0))
        self.activation_count = float(metadata.get('activation_count', self.use_count))
        self.type = metadata.get('type', 'dynamic')
        self.pinned = bool(metadata.get('pinned', self.type == 'permanent'))
        self.resolved = bool(metadata.get('resolved', False))
        self.digested = bool(metadata.get('digested', False))
        self.content = content

    def _generate_id(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"mem_{timestamp}"

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except Exception:
                pass
        return datetime.now()

    def calculate_score(self) -> float:
        """??????permanent/feel/plan/letter ?????????????"""
        if self.type in ('permanent', 'feel', 'plan', 'letter') or self.pinned:
            return 50.0

        hours_since_active = max((datetime.now() - self.last_active).total_seconds() / 3600, 0)
        time_weight = math.exp(-0.02 * (hours_since_active / 24))
        activation_bonus = 1 + min(self.activation_count * 0.08, 2.0)
        emotion_bonus = 1 + (self.arousal * 0.25)

        state_factor = 1.0
        if self.resolved:
            state_factor *= 0.05 if self.digested else 0.3

        return self.importance * time_weight * activation_bonus * emotion_bonus * state_factor

    def mark_used(self):
        now = datetime.now()
        self.last_used = now
        self.last_active = now
        self.use_count += 1
        self.activation_count += 1

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'domain': self.domain,
            'importance': self.importance,
            'valence': self.valence,
            'arousal': self.arousal,
            'tags': self.tags,
            'created': self.created.isoformat(),
            'last_used': self.last_used.isoformat(),
            'last_active': self.last_active.isoformat(),
            'use_count': self.use_count,
            'activation_count': self.activation_count,
            'type': self.type,
            'pinned': self.pinned,
            'resolved': self.resolved,
            'digested': self.digested,
            'content': self.content,
            'score': self.calculate_score()
        }

    def to_yaml_frontmatter(self) -> str:
        metadata = {
            'id': self.id,
            'name': self.name,
            'domain': self.domain,
            'importance': self.importance,
            'valence': self.valence,
            'arousal': self.arousal,
            'tags': self.tags,
            'created': self.created.isoformat(),
            'last_used': self.last_used.isoformat(),
            'last_active': self.last_active.isoformat(),
            'use_count': self.use_count,
            'activation_count': self.activation_count,
            'type': self.type,
            'pinned': self.pinned,
            'resolved': self.resolved,
            'digested': self.digested,
        }
        frontmatter = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip()
        return f"---\n{frontmatter}\n---\n\n{self.content}\n"


class MemorySystem:
    """Ombre-Brain??????"""

    def __init__(self):
        self.memory_dir = Path(MEMORY_DIR)
        self._ensure_directories()

    def _ensure_directories(self):
        (self.memory_dir / "permanent").mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "dynamic").mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "feel").mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "plans" / "active").mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "letters" / "history").mkdir(parents=True, exist_ok=True)
        (self.memory_dir / "archive").mkdir(parents=True, exist_ok=True)

    def _bucket_paths(self, include_archive: bool = False) -> List[Path]:
        paths = [
            self.memory_dir / "permanent",
            self.memory_dir / "dynamic",
            self.memory_dir / "feel",
            self.memory_dir / "plans" / "active",
            self.memory_dir / "letters" / "history",
        ]
        if include_archive:
            paths.append(self.memory_dir / "archive")
        return paths

    def _infer_type_from_path(self, file_path: Path) -> str:
        parts = set(file_path.parts)
        if 'plans' in parts:
            return 'plan'
        if 'letters' in parts:
            return 'letter'
        return file_path.parent.name

    def load_memory_file(self, file_path: Path) -> Optional[Memory]:
        try:
            content = file_path.read_text(encoding='utf-8')

            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1]) or {}
                    metadata.setdefault('type', self._infer_type_from_path(file_path))
                    body = parts[2].strip()
                    return Memory(str(file_path), metadata, body)

            metadata = {'type': self._infer_type_from_path(file_path)}
            return Memory(str(file_path), metadata, content.strip())

        except Exception as e:
            print(f"???????? {file_path}: {e}")
            return None

    def load_all_memories(self, include_archive: bool = False) -> List[Memory]:
        memories = []
        for dir_path in self._bucket_paths(include_archive):
            if dir_path.exists():
                for file_path in dir_path.rglob("*.md"):
                    memory = self.load_memory_file(file_path)
                    if memory:
                        memories.append(memory)
        return memories

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", text.lower())

    def _query_terms(self, query: str) -> List[str]:
        tokens = [token for token in self._tokenize(query) if token not in STOP_TOKENS]
        cjk = [token for token in tokens if re.fullmatch(r"[\u4e00-\u9fff]", token)]
        latin = [token for token in tokens if not re.fullmatch(r"[\u4e00-\u9fff]", token)]

        terms = list(latin)
        if len(cjk) == 1:
            terms.append(cjk[0])
        elif len(cjk) >= 2:
            joined = "".join(cjk)
            terms.append(joined)
            terms.extend(joined[index:index + 2] for index in range(len(joined) - 1))

        seen = set()
        result = []
        for term in terms:
            if term and term not in seen:
                seen.add(term)
                result.append(term)
        return result

    def _keyword_score(self, query: str, memory: Memory) -> float:
        query_tokens = self._query_terms(query)
        if not query_tokens:
            return 0.0

        haystacks = [
            (memory.name, 3.0),
            (memory.domain, 2.5),
            (' '.join(memory.tags), 2.0),
            (direct_seed_text(memory.content)[:1000], 1.0),
        ]

        score = 0.0
        for token in query_tokens:
            for text, weight in haystacks:
                if token and token in str(text).lower():
                    score += weight
                    break
        return min(score / max(len(query_tokens), 1), 10.0)

    def _vector_scores(self, query: str, n_results: int) -> Dict[str, float]:
        try:
            results = memory_collection.query(query_texts=[query], n_results=n_results)
            ids = results.get('ids', [[]])[0]
            distances = results.get('distances', [[]])[0] if results.get('distances') else []
            scores = {}
            for index, mem_id in enumerate(ids):
                distance = distances[index] if index < len(distances) else 1.0
                scores[mem_id] = max(0.0, 1.0 - float(distance)) * 10
            return scores
        except Exception as e:
            print(f"??????: {e}")
            return {}

    def _search_base_score(self, memory: Memory) -> float:
        return min(memory.calculate_score(), 10.0)

    def _passes_direct_relevance(self, keyword: float, vector: float) -> bool:
        vector_threshold = _env_float("MEMORY_DIRECT_VECTOR_THRESHOLD", 8.0, 0.0, 10.0)
        return keyword > 0 or vector >= vector_threshold

    def _combined_search_score(self, keyword: float, vector: float, base: float) -> float:
        base_weight = _env_float("MEMORY_SEARCH_BASE_WEIGHT", 0.25, 0.0, 1.0)
        return (keyword * 2.0) + (vector * 1.5) + (base * base_weight)

    def search_memories(
        self,
        query: str,
        top_k: int = 5,
        include_feel: bool = False,
        include_archive: bool = False,
        domain: str = "",
        tags: List[str] = None,
        importance_min: int = -1,
        touch: bool = True
    ) -> List[Memory]:
        """????? + ???? + ???????????????feel/plan/letter?"""
        tags = tags or []
        all_memories = self.load_all_memories(include_archive=include_archive)
        candidates = []

        for memory in all_memories:
            if memory.type in ('feel', 'plan', 'letter') and not include_feel:
                continue
            if domain and memory.domain != domain and memory.type != domain:
                continue
            if tags and not set(tags).intersection(set(memory.tags)):
                continue
            if importance_min >= 1 and memory.importance < importance_min:
                continue
            candidates.append(memory)

        vector_scores = self._vector_scores(query, max(top_k * 4, 10)) if query else {}
        scored = []
        for memory in candidates:
            keyword = self._keyword_score(query, memory)
            vector = vector_scores.get(memory.id, 0.0)
            base = self._search_base_score(memory)
            if not self._passes_direct_relevance(keyword, vector):
                continue
            final_score = self._combined_search_score(keyword, vector, base)
            scored.append((final_score, memory))

        scored.sort(key=lambda item: item[0], reverse=True)
        found_memories = [memory for _, memory in scored[:top_k]]

        if touch:
            for memory in found_memories:
                if memory.type in ('feel', 'plan', 'letter'):
                    continue
                memory.mark_used()
                self.save_memory(memory)

        return found_memories

    def explain_search_memories(
        self,
        query: str,
        top_k: int = 5,
        include_feel: bool = False,
        include_archive: bool = False,
        domain: str = "",
        tags: List[str] = None,
        importance_min: int = -1,
    ) -> List[Dict[str, Any]]:
        """Return search results with scoring details without touching memory files."""
        tags = tags or []
        all_memories = self.load_all_memories(include_archive=include_archive)
        candidates = []

        for memory in all_memories:
            if memory.type in ('feel', 'plan', 'letter') and not include_feel:
                continue
            if domain and memory.domain != domain and memory.type != domain:
                continue
            if tags and not set(tags).intersection(set(memory.tags)):
                continue
            if importance_min >= 1 and memory.importance < importance_min:
                continue
            candidates.append(memory)

        vector_scores = self._vector_scores(query, max(top_k * 4, 10)) if query else {}
        explained = []
        for memory in candidates:
            keyword = self._keyword_score(query, memory)
            vector = vector_scores.get(memory.id, 0.0)
            base = self._search_base_score(memory)
            relevance_passed = self._passes_direct_relevance(keyword, vector)
            if not relevance_passed:
                continue
            final_score = self._combined_search_score(keyword, vector, base)
            explained.append({
                "memory": memory,
                "keyword_score": round(keyword, 3),
                "vector_score": round(vector, 3),
                "base_score": round(base, 3),
                "final_score": round(final_score, 3),
                "relevance_passed": relevance_passed,
                "importance": memory.importance,
                "use_count": memory.use_count,
                "pinned": memory.pinned,
                "type": memory.type,
            })

        explained.sort(key=lambda item: item["final_score"], reverse=True)
        return explained[:top_k]
    def save_memory(self, memory: Memory) -> bool:
        try:
            file_path = Path(memory.file_path) if memory.file_path else self._path_for_new_memory(memory)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(memory.to_yaml_frontmatter(), encoding='utf-8')
            memory.file_path = str(file_path)

            try:
                memory_collection.upsert(
                    ids=[memory.id],
                    documents=[direct_seed_text(memory.content)],
                    metadatas=[{
                        'importance': memory.importance,
                        'type': memory.type,
                        'domain': memory.domain,
                        'tags': ','.join(memory.tags)
                    }]
                )
            except Exception as e:
                print(f"?????????: {e}")

            return True

        except Exception as e:
            print(f"??????: {e}")
            return False

    def _path_for_new_memory(self, memory: Memory) -> Path:
        if memory.type == 'plan':
            return self.memory_dir / "plans" / "active" / f"{memory.id}.md"
        if memory.type == 'letter':
            return self.memory_dir / "letters" / "history" / f"{memory.id}.md"
        dir_name = memory.type if memory.type in ('permanent', 'dynamic', 'feel', 'archive') else 'dynamic'
        return self.memory_dir / dir_name / f"{memory.id}.md"

    def create_memory(
        self,
        content: str,
        importance: int = 5,
        mem_type: str = "dynamic",
        tags: List[str] = None,
        valence: float = 0.5,
        arousal: float = 0.5,
        name: str = "",
        domain: str = ""
    ) -> Memory:
        now = datetime.now().isoformat()
        metadata = {
            'name': name,
            'domain': domain,
            'importance': min(max(int(importance), 1), 10),
            'type': mem_type,
            'tags': tags or [],
            'valence': min(max(float(valence), 0.0), 1.0),
            'arousal': min(max(float(arousal), 0.0), 1.0),
            'created': now,
            'last_used': now,
            'last_active': now,
            'use_count': 0,
            'activation_count': 0,
            'pinned': mem_type == 'permanent',
            'resolved': False,
            'digested': False,
        }

        memory = Memory(None, metadata, content)
        if not memory.name:
            memory.name = memory.id
        self.save_memory(memory)
        return memory

    def archive_old_memories(self, score_threshold: float = 2.0):
        memories = self.load_all_memories()

        for memory in memories:
            if memory.type != 'dynamic':
                continue

            if memory.calculate_score() < score_threshold:
                old_path = Path(memory.file_path)
                new_path = self.memory_dir / "archive" / old_path.name

                try:
                    old_path.rename(new_path)
                    memory.file_path = str(new_path)
                    memory.type = 'archive'
                    self.save_memory(memory)
                    print(f"????: {memory.id}")
                except Exception as e:
                    print(f"???? {memory.id}: {e}")

    def format_memories_for_claude(self, memories: List[Memory]) -> str:
        if not memories:
            return "(No relevant memories yet)"

        text = "# My memories\n\n"

        for memory in memories:
            tags_str = ', '.join(memory.tags) if memory.tags else ''
            title = memory.name or memory.id

            text += f"## {title}\n"
            if tags_str:
                text += f"*??: {tags_str}*\n\n"
            text += f"{memory.content}\n\n---\n\n"

        return text

    def get_relevant_memory_context(self, query: str, top_k: int = 6) -> str:
        memories = self.search_memories(query=query, top_k=top_k)
        return self.format_memories_for_claude(memories)


# ????
memory_system = MemorySystem()


def get_memory_summary() -> str:
    """?????????????????"""
    memories = memory_system.load_all_memories()
    memories = [m for m in memories if m.type not in ('feel', 'plan', 'letter')]
    memories.sort(key=lambda m: m.calculate_score(), reverse=True)
    return memory_system.format_memories_for_claude(memories[:5])


def get_relevant_memory_summary(query: str, top_k: int = 6) -> str:
    """???????????"""
    return memory_system.get_relevant_memory_context(query, top_k=top_k)

