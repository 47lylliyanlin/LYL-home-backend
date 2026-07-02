"""Short-term recall cooldown for surfaced memory buckets."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

RUNTIME_DIR = Path("./runtime")
COOLDOWN_PATH = RUNTIME_DIR / "recall_cooldown.json"


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return min(max(value, min_value), max_value)


def recall_cooldown_enabled() -> bool:
    return _env_bool("MEMORY_RECALL_COOLDOWN_ENABLED", True)


def recall_cooldown_minutes() -> int:
    return _env_int("MEMORY_RECALL_COOLDOWN_MINUTES", 45, 0, 24 * 60)


def _ensure_runtime_dir() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> datetime:
    return datetime.now()


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _load() -> Dict:
    _ensure_runtime_dir()
    if not COOLDOWN_PATH.exists():
        return {"items": {}}
    try:
        data = json.loads(COOLDOWN_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"items": {}}
    if not isinstance(data, dict):
        return {"items": {}}
    data.setdefault("items", {})
    return data


def _save(data: Dict) -> None:
    _ensure_runtime_dir()
    COOLDOWN_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _prune(data: Dict) -> Dict:
    ttl = recall_cooldown_minutes()
    if ttl <= 0:
        data["items"] = {}
        return data
    cutoff = _now() - timedelta(minutes=ttl)
    kept = {}
    for memory_id, item in (data.get("items") or {}).items():
        recalled_at = _parse_time(item.get("last_recalled_at"))
        if recalled_at and recalled_at >= cutoff:
            kept[memory_id] = item
    data["items"] = kept
    return data


def is_recently_recalled(memory_id: str) -> bool:
    if not recall_cooldown_enabled():
        return False
    data = _prune(_load())
    item = data.get("items", {}).get(memory_id)
    if not item:
        return False
    recalled_at = _parse_time(item.get("last_recalled_at"))
    if not recalled_at:
        return False
    return _now() - recalled_at < timedelta(minutes=recall_cooldown_minutes())


def filter_recent_memories(memories: List, min_keep: int = 1) -> Tuple[List, List[Dict]]:
    """Filter memory objects by cooldown, keeping at least min_keep if all are cooled."""
    if not recall_cooldown_enabled() or recall_cooldown_minutes() <= 0:
        return memories, []

    kept = []
    skipped = []
    for memory in memories:
        if is_recently_recalled(memory.id):
            skipped.append({"id": memory.id, "title": memory.name or memory.id})
        else:
            kept.append(memory)

    if not kept and memories and min_keep > 0:
        kept = memories[:min_keep]
        kept_ids = {memory.id for memory in kept}
        skipped = [item for item in skipped if item.get("id") not in kept_ids]
    return kept, skipped


def filter_recent_explained(items: List[Dict], min_keep: int = 1) -> Tuple[List[Dict], List[Dict]]:
    memories = [item.get("memory") for item in items if item.get("memory")]
    kept_memories, skipped = filter_recent_memories(memories, min_keep=min_keep)
    kept_ids = {memory.id for memory in kept_memories}
    return [item for item in items if item.get("memory") and item["memory"].id in kept_ids], skipped


def record_recall(memories: Iterable, source: str) -> None:
    if not recall_cooldown_enabled() or recall_cooldown_minutes() <= 0:
        return
    data = _prune(_load())
    items = data.setdefault("items", {})
    now = _now().isoformat()
    for memory in memories:
        memory_id = getattr(memory, "id", None) if not isinstance(memory, str) else memory
        if not memory_id:
            continue
        existing = items.get(memory_id, {})
        items[memory_id] = {
            "id": memory_id,
            "title": getattr(memory, "name", "") if not isinstance(memory, str) else existing.get("title", ""),
            "source": source,
            "last_recalled_at": now,
            "count": int(existing.get("count", 0)) + 1,
        }
    _save(data)


def recall_cooldown_status(limit: int = 20) -> Dict:
    data = _prune(_load())
    _save(data)
    items = list((data.get("items") or {}).values())
    items.sort(key=lambda item: item.get("last_recalled_at", ""), reverse=True)
    now = _now()
    active = []
    for item in items[:limit]:
        recalled_at = _parse_time(item.get("last_recalled_at"))
        remaining_seconds = 0
        if recalled_at:
            expires_at = recalled_at + timedelta(minutes=recall_cooldown_minutes())
            remaining_seconds = max(int((expires_at - now).total_seconds()), 0)
        active.append({**item, "remaining_seconds": remaining_seconds})
    return {
        "enabled": recall_cooldown_enabled(),
        "ttl_minutes": recall_cooldown_minutes(),
        "count": len(items),
        "active": active,
    }
