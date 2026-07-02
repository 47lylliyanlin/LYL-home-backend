"""Conservative write gate for proposed memory candidates."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Tuple

import yaml

from .bucket_format import direct_seed_text
from .memory import memory_system

CANDIDATES_DIR = Path("./memory/candidates")

TEST_MARKERS = {
    "test",
    "testing",
    "temporary tool test",
    "placeholder",
    "hello world",
    "\u6d4b\u8bd5",
    "\u8bd5\u8bd5",
    "\u968f\u4fbf\u8bd5",
}

EPHEMERAL_MARKERS = {
    "just chatting",
    "small talk",
    "right now only",
    "temporary",
    "for now only",
    "\u968f\u4fbf\u804a\u804a",
    "\u521a\u521a\u8fd9\u53e5",
    "\u4e34\u65f6",
}

PROFILE_TYPES = {"profile_candidate"}
HIGH_RISK_TYPES = {"permanent", "profile_candidate", "I", "darkroom"}


def _truncate(text: str, limit: int = 600) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _normalize(text: str) -> str:
    value = (text or "").lower().strip()
    value = re.sub(r"\s+", " ", value)
    return value


def _terms(text: str) -> List[str]:
    return re.findall(r"[\u4e00-\u9fff]|[a-z0-9_]+", _normalize(text))


def _similarity(left: str, right: str) -> float:
    left_norm = _normalize(left)
    right_norm = _normalize(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm in right_norm or right_norm in left_norm:
        shorter = min(len(left_norm), len(right_norm))
        longer = max(len(left_norm), len(right_norm))
        if shorter >= 18 or (shorter / max(longer, 1)) >= 0.75:
            return 1.0
    sequence = SequenceMatcher(None, left_norm, right_norm).ratio()
    left_terms = set(_terms(left_norm))
    right_terms = set(_terms(right_norm))
    jaccard = 0.0
    if left_terms and right_terms:
        jaccard = len(left_terms & right_terms) / len(left_terms | right_terms)
    return max(sequence, jaccard)


def _candidate_texts() -> List[Tuple[str, str]]:
    if not CANDIDATES_DIR.exists():
        return []
    result: List[Tuple[str, str]] = []
    for path in CANDIDATES_DIR.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
            meta = {}
            body = text
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) == 3:
                    meta = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
            status = str(meta.get("status") or "")
            if status in {"rejected_by_gate", "duplicate", "rejected"}:
                continue
            result.append((str(meta.get("id") or path.stem), body))
        except Exception:
            continue
    return result


def _bucket_texts() -> List[Tuple[str, str]]:
    result: List[Tuple[str, str]] = []
    for memory in memory_system.load_all_memories(include_archive=False):
        result.append((memory.id, str(memory.name) + "\n" + direct_seed_text(memory.content)))
    return result


def _best_duplicate(content: str) -> Dict:
    best = {"id": "", "source": "", "score": 0.0}
    for source, items in (("candidate", _candidate_texts()), ("bucket", _bucket_texts())):
        for item_id, text in items:
            score = _similarity(content, text)
            if score > best["score"]:
                best = {"id": item_id, "source": source, "score": round(score, 3)}
    return best


def evaluate_write_candidate(
    title: str,
    content: str,
    suggested_type: str = "dynamic",
    evidence_ids: List[str] | None = None,
) -> Dict:
    """Return a conservative gate decision for a proposed memory candidate."""
    evidence_ids = evidence_ids or []
    title_norm = _normalize(title)
    content_norm = _normalize(content)
    combined = f"{title_norm} {content_norm}".strip()
    risk_flags: List[str] = []

    if not content_norm:
        return {
            "accepted": False,
            "decision": "rejected",
            "code": "empty_content",
            "reason": "Candidate content is empty.",
            "risk_flags": ["empty"],
            "duplicate": None,
        }

    term_count = len(_terms(content_norm))
    if len(content_norm) < 16 or term_count < 4:
        return {
            "accepted": False,
            "decision": "rejected",
            "code": "too_short",
            "reason": "Candidate is too short to be useful as long-term memory.",
            "risk_flags": ["too_short"],
            "duplicate": None,
        }

    if any(marker in combined for marker in TEST_MARKERS):
        return {
            "accepted": False,
            "decision": "rejected",
            "code": "looks_like_test",
            "reason": "Candidate looks like a test or placeholder memory.",
            "risk_flags": ["test_or_placeholder"],
            "duplicate": None,
        }

    if any(marker in combined for marker in EPHEMERAL_MARKERS):
        return {
            "accepted": False,
            "decision": "rejected",
            "code": "too_ephemeral",
            "reason": "Candidate looks temporary or too tied to the immediate moment.",
            "risk_flags": ["ephemeral"],
            "duplicate": None,
        }

    duplicate = _best_duplicate(str(title) + "\n" + str(content))
    if duplicate["score"] >= 0.9:
        return {
            "accepted": False,
            "decision": "duplicate",
            "code": "duplicate_memory",
            "reason": "Candidate is very similar to an existing active memory or pending candidate.",
            "risk_flags": ["duplicate"],
            "duplicate": duplicate,
        }

    safe_type = (suggested_type or "dynamic").strip()
    if safe_type in PROFILE_TYPES and not evidence_ids:
        return {
            "accepted": False,
            "decision": "rejected",
            "code": "profile_needs_evidence",
            "reason": "Profile facts need evidence before they can enter the candidate queue.",
            "risk_flags": ["profile_without_evidence"],
            "duplicate": duplicate if duplicate["id"] else None,
        }

    if safe_type in HIGH_RISK_TYPES:
        risk_flags.append("high_risk_type")

    return {
        "accepted": True,
        "decision": "accepted",
        "code": "accepted",
        "reason": "Candidate passed the conservative write gate.",
        "risk_flags": risk_flags,
        "duplicate": duplicate if duplicate["score"] >= 0.72 else None,
    }
