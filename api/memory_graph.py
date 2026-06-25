"""
Lightweight memory graph: moments, edges, and detail recall.

This is the first safe layer. It does not auto-split every bucket yet; it gives
Gateway controlled access to details from IDs that were already surfaced.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .memory import Memory, memory_system

GRAPH_DIR = Path("./memory/graph")
MOMENTS_PATH = GRAPH_DIR / "moments.jsonl"
EDGES_PATH = GRAPH_DIR / "edges.jsonl"


def _u(*codes: int) -> str:
    return "".join(chr(code) for code in codes)


DETAIL_RECALL_TRIGGERS = [
    _u(0x5c55, 0x5f00),  # expand
    _u(0x8be6, 0x7ec6),  # detail
    _u(0x8bb2, 0x8bb2),  # talk about it
    _u(0x7ee7, 0x7eed),  # continue
    _u(0x521a, 0x624d, 0x90a3, 0x4e2a),  # that one just now
    _u(0x4e3a, 0x4ec0, 0x4e48),  # why
    _u(0x786e, 0x8ba4),  # confirm
    _u(0x559c, 0x6b22, 0x8fd9, 0x6b21),  # like this time
]

EDGE_TYPES = {
    "updates",
    "supports",
    "blocks",
    "promises",
    "continues",
    "evidence",
    "diffuses",
}


def _ensure_graph_dir():
    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    for path in [MOMENTS_PATH, EDGES_PATH]:
        if not path.exists():
            path.write_text("", encoding="utf-8")


def needs_detail_recall(user_message: str) -> bool:
    return any(trigger in user_message for trigger in DETAIL_RECALL_TRIGGERS)


def _truncate(text: str, limit: int = 1200) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _load_jsonl(path: Path) -> List[Dict]:
    _ensure_graph_dir()
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def _append_jsonl(path: Path, item: Dict):
    _ensure_graph_dir()
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def create_moment(bucket_id: str, content: str, title: str = "", tags: Optional[List[str]] = None) -> Dict:
    moment = {
        "id": f"moment_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "bucket_id": bucket_id,
        "title": title or bucket_id,
        "content": content,
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
    }
    _append_jsonl(MOMENTS_PATH, moment)
    return moment


def create_edge(source_id: str, target_id: str, edge_type: str, note: str = "") -> Dict:
    if edge_type not in EDGE_TYPES:
        raise ValueError(f"Unsupported edge type: {edge_type}")
    edge = {
        "id": f"edge_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
        "source_id": source_id,
        "target_id": target_id,
        "type": edge_type,
        "note": note,
        "created_at": datetime.now().isoformat(),
    }
    _append_jsonl(EDGES_PATH, edge)
    return edge


def list_moments(bucket_id: Optional[str] = None) -> List[Dict]:
    moments = _load_jsonl(MOMENTS_PATH)
    if bucket_id:
        moments = [item for item in moments if item.get("bucket_id") == bucket_id]
    return moments


def list_edges(source_id: Optional[str] = None, target_id: Optional[str] = None) -> List[Dict]:
    edges = _load_jsonl(EDGES_PATH)
    if source_id:
        edges = [item for item in edges if item.get("source_id") == source_id]
    if target_id:
        edges = [item for item in edges if item.get("target_id") == target_id]
    return edges


def _memory_by_id(memory_id: str) -> Optional[Memory]:
    for memory in memory_system.load_all_memories(include_archive=True):
        if memory.id == memory_id:
            return memory
    return None


def detail_context_from_ids(memory_ids: List[str], max_items: int = 3) -> str:
    parts = []
    seen = set()
    for memory_id in memory_ids:
        if memory_id in seen:
            continue
        seen.add(memory_id)
        memory = _memory_by_id(memory_id)
        if not memory:
            continue
        moments = list_moments(bucket_id=memory.id)
        edge_notes = list_edges(source_id=memory.id)[:5]
        moment_text = "\n".join(
            f"  - moment_id: {item.get('id')} | {item.get('title')}: {_truncate(item.get('content', ''), 400)}"
            for item in moments[:5]
        ) or "  - no moments recorded yet"
        edge_text = "\n".join(
            f"  - {item.get('type')} -> {item.get('target_id')}: {item.get('note', '')}"
            for item in edge_notes
        ) or "  - no edges recorded yet"
        parts.append(
            f"## Detail bucket: {memory.id}\n"
            f"title: {memory.name or memory.id}\n"
            f"type: {memory.type}\n"
            f"tags: {', '.join(memory.tags) if memory.tags else 'none'}\n\n"
            f"content:\n{_truncate(memory.content, 1600)}\n\n"
            f"moments:\n{moment_text}\n\n"
            f"edges:\n{edge_text}"
        )
        if len(parts) >= max_items:
            break
    return "\n\n---\n\n".join(parts).strip()



def diffuse_from_seed_ids(seed_ids: List[str], max_items: int = 3) -> List[Dict]:
    """Return a small graph neighborhood only after reliable direct seeds exist."""
    if not seed_ids:
        return []
    edges = list_edges()
    moments = {item.get("id"): item for item in list_moments()}
    memories = {memory.id: memory for memory in memory_system.load_all_memories(include_archive=True)}
    seed_set = set(seed_ids)
    allowed = {"updates", "supports", "blocks", "promises", "continues", "diffuses"}
    result = []
    seen = set()
    for edge in edges:
        source = edge.get("source_id")
        target = edge.get("target_id")
        if edge.get("type") not in allowed:
            continue
        if source not in seed_set and target not in seed_set:
            continue
        related_id = target if source in seed_set else source
        if not related_id or related_id in seen or related_id in seed_set:
            continue
        seen.add(related_id)
        item = {
            "id": related_id,
            "via_edge": edge.get("type"),
            "edge_note": edge.get("note", ""),
            "source_seed_id": source if source in seed_set else target,
            "confidence": "diffused",
        }
        if related_id in memories:
            memory = memories[related_id]
            item.update({
                "kind": "bucket",
                "title": memory.name or memory.id,
                "type": memory.type,
                "tags": memory.tags,
                "preview": _truncate(memory.content, 360),
            })
        elif related_id in moments:
            moment = moments[related_id]
            item.update({
                "kind": "moment",
                "title": moment.get("title") or related_id,
                "bucket_id": moment.get("bucket_id"),
                "tags": moment.get("tags", []),
                "preview": _truncate(moment.get("content", ""), 360),
            })
        else:
            item.update({"kind": "unknown", "title": related_id, "preview": ""})
        result.append(item)
        if len(result) >= max_items:
            break
    return result


def render_diffused_context(items: List[Dict]) -> str:
    if not items:
        return "(none)"
    lines = []
    for item in items:
        lines.append(
            f"- id: {item.get('id')}\n"
            f"  kind: {item.get('kind')}\n"
            f"  via: {item.get('via_edge')} from {item.get('source_seed_id')}\n"
            f"  title: {item.get('title')}\n"
            f"  confidence: diffused-low\n"
            f"  preview: {_truncate(item.get('preview', ''), 360)}"
        )
    return "\n".join(lines)


def graph_status() -> Dict:
    moments = _load_jsonl(MOMENTS_PATH)
    edges = _load_jsonl(EDGES_PATH)
    return {
        "moments": len(moments),
        "edges": len(edges),
        "graph_dir": str(GRAPH_DIR),
    }
