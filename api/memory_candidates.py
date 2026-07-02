"""Pending memory candidates proposed by the internal tool loop."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

CANDIDATES_DIR = Path("./memory/candidates")
ALLOWED_TYPES = {"dynamic", "permanent", "profile_candidate", "feel", "I", "darkroom"}


def _ensure_dir() -> None:
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)


def _truncate(text: str, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _slug(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_\-]+", "_", (text or "").strip().lower())
    return value.strip("_")[:48] or "memory"


def _safe_type(value: str) -> str:
    candidate_type = (value or "dynamic").strip()
    return candidate_type if candidate_type in ALLOWED_TYPES else "dynamic"


def _parse_candidate(path: Path) -> Dict:
    text = path.read_text(encoding="utf-8")
    meta: Dict = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].strip()
    stat = path.stat()
    return {
        "id": meta.get("id") or path.stem,
        "title": meta.get("title") or path.stem,
        "suggested_type": meta.get("suggested_type") or "dynamic",
        "status": meta.get("status") or "pending",
        "reason": meta.get("reason") or "",
        "source": meta.get("source") or "unknown",
        "confidence": meta.get("confidence"),
        "evidence_ids": meta.get("evidence_ids") or [],
        "created_at": meta.get("created_at") or datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "updated_at": meta.get("updated_at") or datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "file": str(path),
        "name": path.name,
        "preview": _truncate(body, 700),
    }


def create_memory_candidate(
    title: str,
    content: str,
    suggested_type: str = "dynamic",
    reason: str = "",
    source: str = "internal_tool",
    evidence_ids: Optional[List[str]] = None,
    confidence: float = 0.5,
) -> Dict:
    """Create a pending memory candidate without promoting it into long-term memory."""
    _ensure_dir()
    safe_title = _truncate(title or "Untitled memory candidate", 120)
    safe_content = _truncate(content or "", 4000)
    safe_reason = _truncate(reason or "", 600)
    if not safe_content:
        return {"ok": False, "error": "content is required"}

    evidence_ids = [_truncate(str(item), 160) for item in (evidence_ids or []) if str(item).strip()]
    now = datetime.now().isoformat()
    candidate_id = f"memory_candidate_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{_slug(safe_title)}"
    path = CANDIDATES_DIR / f"{candidate_id}.md"
    meta = {
        "id": candidate_id,
        "title": safe_title,
        "suggested_type": _safe_type(suggested_type),
        "status": "pending",
        "reason": safe_reason,
        "source": source,
        "confidence": max(0.0, min(float(confidence or 0.5), 1.0)),
        "evidence_ids": evidence_ids,
        "created_at": now,
        "updated_at": now,
    }
    frontmatter = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    body = f"""---
{frontmatter}
---

# {safe_title}

## Proposed Memory

{safe_content}

## Review Note

This is a pending memory candidate. It is not confirmed long-term memory until reviewed.
"""
    path.write_text(body, encoding="utf-8")
    return {"ok": True, "candidate": _parse_candidate(path)}


def list_memory_candidates(limit: int = 50) -> List[Dict]:
    _ensure_dir()
    paths = sorted(CANDIDATES_DIR.glob("*.md"), key=lambda item: item.stat().st_mtime, reverse=True)
    return [_parse_candidate(path) for path in paths[: max(1, min(int(limit or 50), 200))]]
