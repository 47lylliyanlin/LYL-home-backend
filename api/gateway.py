"""
Ombre Gateway for Kiro chat turns.

The Gateway prepares quiet memory context before the upstream model call,
then records the turn and asks the memory system to consolidate it after reply.
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .memory import Memory, memory_system
from .memory_extraction import extract_memory_from_conversation, save_extracted_memory
from .profile import profile_manager
from .memory_graph import create_edge, create_moment, detail_context_from_ids, diffuse_from_seed_ids, needs_detail_recall, render_diffused_context
from .darkroom import darkroom_door_context
from .dream import relationship_weather_context
from .word_map import render_weak_concept_hints, weak_concept_hints

RUNTIME_DIR = Path("./runtime")
RECENT_TURNS_PATH = RUNTIME_DIR / "recent_turns.jsonl"
SESSIONS_DIR = RUNTIME_DIR / "sessions"
LAST_CONTEXT_PATH = RUNTIME_DIR / "last_injected_context.json"


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


def _safe_session_id(session_id: Optional[str]) -> str:
    value = (session_id or "default").strip()
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:80].strip("._-")
    return value or "default"


def _session_turns_path(session_id: Optional[str]) -> Path:
    return SESSIONS_DIR / f"{_safe_session_id(session_id)}.jsonl"

def _u(*codes: int) -> str:
    return "".join(chr(code) for code in codes)


JUST_NOW_TRIGGERS = [
    _u(0x521a, 0x521a),  # just now
    _u(0x521a, 0x624d),  # a moment ago
    _u(0x521a, 0x624d, 0x8bf4),  # just said
    _u(0x521a, 0x624d, 0x63d0),  # just mentioned
    _u(0x4e0a, 0x4e00, 0x53e5),  # previous sentence
    _u(0x4e0a, 0x53e5, 0x8bdd),  # previous line/sentence
    _u(0x524d, 0x4e00, 0x53e5),  # prior sentence
    _u(0x4e0a, 0x4e00, 0x6761),  # previous item/message
    _u(0x4e0a, 0x4e00, 0x8f6e),  # previous turn
    _u(0x6697, 0x53f7),  # code word
    _u(0x5173, 0x952e, 0x8bcd),  # keyword
    _u(0x8bb0, 0x4f4f, 0x54ea, 0x4e2a),  # which thing did you remember
    _u(0x6211, 0x8ba9, 0x4f60, 0x8bb0, 0x4f4f),  # I asked you to remember
    _u(0x521a, 0x63d0, 0x5230),  # just mentioned
    _u(0x521a, 0x8bf4),  # just said
]

WAKE_TAG_HINTS = {
    "relationship",
    "girlfriend",
    "identity",
    "how-i-should-call-you",
    "what-you-value",
}
WAKE_DOMAIN_HINTS = {"relationship", "identity", "profile", "preference"}


@dataclass
class PreparedTurn:
    system_prompt: str
    injected_context: Dict
    messages: List[Dict[str, str]]


def _ensure_runtime_dir():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _truncate(text: str, limit: int = 900) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _memory_title(memory: Memory) -> str:
    return memory.name or memory.id


def _render_memory(memory: Memory, limit: int = 900) -> str:
    tags = ", ".join(memory.tags) if memory.tags else "none"
    return (
        f"- id: {memory.id}\n"
        f"  title: {_memory_title(memory)}\n"
        f"  type: {memory.type}\n"
        f"  tags: {tags}\n"
        f"  content: {_truncate(memory.content, limit)}"
    )


def _memory_ref(memory: Memory, source: str) -> Dict:
    return {
        "id": memory.id,
        "title": _memory_title(memory),
        "type": memory.type,
        "tags": memory.tags,
        "source": source,
    }


def _dedupe_memories(memories: List[Memory]) -> List[Memory]:
    seen = set()
    result = []
    for memory in memories:
        if memory.id in seen:
            continue
        seen.add(memory.id)
        result.append(memory)
    return result


def needs_just_now_context(user_message: str) -> bool:
    return any(trigger in user_message for trigger in JUST_NOW_TRIGGERS)


def _read_turns(path: Path, limit: int = 10) -> List[Dict]:
    if not path.exists():
        return []

    turns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            turns.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return turns[-limit:]


def load_recent_turns(limit: int = 10, session_id: Optional[str] = None) -> List[Dict]:
    _ensure_runtime_dir()
    path = _session_turns_path(session_id) if session_id else RECENT_TURNS_PATH
    return _read_turns(path, limit=limit)


def _previous_session_path(session_id: Optional[str]) -> Optional[Path]:
    _ensure_runtime_dir()
    current = _session_turns_path(session_id).resolve()
    candidates = []
    for path in SESSIONS_DIR.glob("*.jsonl"):
        try:
            if path.resolve() == current or path.stat().st_size <= 0:
                continue
            candidates.append(path)
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0]


def load_previous_session_turns(session_id: Optional[str], limit: int = 4) -> tuple[List[Dict], str]:
    path = _previous_session_path(session_id)
    if not path:
        return [], ""
    return _read_turns(path, limit=limit), path.stem


def record_chat_turn(user_message: str, assistant_message: str, session_id: Optional[str] = None):
    _ensure_runtime_dir()
    now = datetime.now().isoformat()
    new_items = [
        {"role": "user", "content": user_message, "timestamp": now},
        {"role": "assistant", "content": assistant_message, "timestamp": now},
    ]

    for path in [RECENT_TURNS_PATH, _session_turns_path(session_id)]:
        existing = _read_turns(path, limit=80)
        existing.extend(new_items)
        existing = existing[-80:]
        path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in existing) + "\n",
            encoding="utf-8",
        )


def build_wake_memories(limit: int = 2) -> List[Memory]:
    memories = memory_system.load_all_memories(include_archive=False)
    candidates = []
    for memory in memories:
        if memory.type != "permanent":
            continue
        tag_hit = bool(set(memory.tags).intersection(WAKE_TAG_HINTS))
        domain_hit = memory.domain in WAKE_DOMAIN_HINTS
        if tag_hit or (domain_hit and memory.importance >= 0.85):
            candidates.append(memory)

    candidates.sort(key=lambda item: (item.importance, item.calculate_score()), reverse=True)
    return candidates[:limit]


def build_recent_continuity(limit: int = 3) -> List[Memory]:
    memories = memory_system.load_all_memories(include_archive=False)
    dynamic = [memory for memory in memories if memory.type == "dynamic"]
    dynamic.sort(key=lambda item: item.last_active, reverse=True)
    return dynamic[:limit]


def build_scene_memories(user_message: str, limit: int = 5, exclude_ids: Optional[set] = None) -> List[Memory]:
    exclude_ids = exclude_ids or set()
    memories = memory_system.search_memories(user_message, top_k=limit + len(exclude_ids), touch=True)
    return [memory for memory in memories if memory.id not in exclude_ids][:limit]


def render_recent_turns(turns: List[Dict], char_limit: int = 180) -> str:
    if not turns:
        return "(none)"
    lines = []
    for item in turns:
        role = item.get("role", "unknown")
        content = _truncate(item.get("content", ""), char_limit)
        lines.append(f"- {role}: {content}")
    return "\n".join(lines)


def build_chat_messages(user_message: str, history_turns: List[Dict], char_limit: int) -> List[Dict[str, str]]:
    messages = []
    for item in history_turns:
        role = item.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = _truncate(item.get("content", ""), char_limit)
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages



def _context_layers(profile_context: str, weather_context: str, darkroom_context: str, wake_context: str, previous_session_context: str, just_now_turns: List[Dict], scene_memories: List[Memory], detail_context: str) -> List[Dict]:
    return [
        {"name": "Profile Wake", "used": bool(profile_context and profile_context != "(none)"), "count": 1 if profile_context and profile_context != "(none)" else 0, "role": "stable posture"},
        {"name": "Relationship Weather", "used": bool(weather_context and weather_context != "(none)"), "count": 1 if weather_context and weather_context != "(none)" else 0, "role": "tone"},
        {"name": "Darkroom Door", "used": bool(darkroom_context and darkroom_context != "(none)"), "count": 1 if darkroom_context and darkroom_context != "(none)" else 0, "role": "private-state signal"},
        {"name": "Wake Anchors", "used": wake_context != "(none)", "count": 0 if wake_context == "(none)" else wake_context.count("- id:"), "role": "optional anchor"},
        {"name": "Previous Session", "used": previous_session_context != "(none)", "count": 1 if previous_session_context != "(none)" else 0, "role": "new-session continuity"},
        {"name": "Just Now", "used": bool(just_now_turns), "count": len(just_now_turns), "role": "recent chat"},
        {"name": "Scene Memory", "used": bool(scene_memories), "count": len(scene_memories), "role": "direct seed"},
        {"name": "Graph Diffusion", "used": False, "count": 0, "role": "low-confidence neighbor"},
        {"name": "Word Map Hints", "used": False, "count": 0, "role": "weak concept navigation"},
        {"name": "Detail Recall", "used": detail_context != "(none)", "count": 1 if detail_context != "(none)" else 0, "role": "follow-up detail"},
    ]


def build_system_prompt(profile_context: str, weather_context: str, darkroom_context: str, wake_context: str, previous_session_context: str, just_now_context: str, scene_context: str, diffused_context: str, word_hint_context: str, detail_context: str) -> str:
    sections = ["You are Kiro, talking with Bao Bao in a close, natural relationship."]

    optional_sections = [
        ("Profile wake context: stable portraits and recent continuity.", profile_context),
        ("Relationship weather: shallow Dream Light summary.", weather_context),
        ("Darkroom door state: private internal reflection status only, never note contents.", darkroom_context),
        ("Optional wake anchors: a few reliable memories that help me wake up without noise.", wake_context),
        ("Previous session context: recent context from the last session, used only to help a new session continue naturally.", previous_session_context),
        ("Just-now chat context: use this first for questions about what just happened.", just_now_context),
        ("Scene memory context: directly relevant memories for this turn.", scene_context),
        ("Diffused memory context: low-confidence graph neighbors. Use only as a light reminder after direct memory is relevant.", diffused_context),
        ("Word Map hints: weak concept navigation only, never evidence.", word_hint_context),
        ("Detail recall context: only use this when she asks to expand something already surfaced.", detail_context),
    ]

    for title, content in optional_sections:
        if content and content != "(none)":
            sections.append(f"{title}\n{content}")

    if _env_bool("MEMORY_RULES_ENABLED", False):
        sections.append(
            "Memory-use rules:\n"
            "- Use memory silently as background. Answer the current message first.\n"
            "- Do not mention memory retrieval unless Bao Bao asks.\n"
            "- For just-now questions, prefer recent chat over long-term memory."
        )

    return "\n\n".join(sections) + "\n"


def prepare_chat_turn(
    user_message: str,
    session_id: Optional[str] = None,
    recent_turns_count: Optional[int] = None,
    recent_char_limit: Optional[int] = None,
) -> PreparedTurn:
    _ensure_runtime_dir()

    recent_turns_count = recent_turns_count if recent_turns_count is not None else _env_int("MEMORY_RECENT_TURNS", 4, 0, 20)
    recent_char_limit = recent_char_limit if recent_char_limit is not None else _env_int("MEMORY_RECENT_CHAR_LIMIT", 180, 40, 1000)
    recent_turns_count = min(max(int(recent_turns_count), 0), 20)
    recent_char_limit = min(max(int(recent_char_limit), 40), 1000)

    history_limit = recent_turns_count * 2
    session_turns = load_recent_turns(limit=max(history_limit, 1), session_id=session_id) if history_limit else []
    is_new_session = len(session_turns) == 0

    wake_memories = build_wake_memories() if is_new_session else []
    wake_all = _dedupe_memories(wake_memories)
    wake_ids = {memory.id for memory in wake_all}

    detail_requested = needs_detail_recall(user_message)
    just_now_triggered = needs_just_now_context(user_message)
    just_now_turns = session_turns if (just_now_triggered or detail_requested) else []
    scene_memories = [] if (just_now_turns or detail_requested) else build_scene_memories(user_message, exclude_ids=wake_ids)

    profile_context = "(none)"
    weather_context = relationship_weather_context() if is_new_session else "(none)"
    darkroom_context = darkroom_door_context() if is_new_session else "(none)"
    wake_context = "\n".join(_render_memory(memory, 500) for memory in wake_all[:2]) or "(none)"

    previous_session_turns = []
    previous_session_id = ""
    previous_session_source = "none"
    if is_new_session and _env_bool("PREVIOUS_SESSION_CONTEXT_ENABLED", True):
        previous_limit = _env_int("PREVIOUS_SESSION_TURNS", 2, 0, 10) * 2
        if previous_limit:
            previous_session_turns, previous_session_id = load_previous_session_turns(session_id, limit=previous_limit)
        if previous_session_turns:
            previous_session_context = render_recent_turns(previous_session_turns, char_limit=recent_char_limit)
            previous_session_source = "previous_session"
        else:
            recent_continuity = profile_manager.get_profiles().get("recent_continuity", "")
            fallback_limit = _env_int("RECENT_CONTINUITY_FALLBACK_LIMIT", 500, 120, 1200)
            previous_session_context = _truncate(recent_continuity, fallback_limit) if recent_continuity else "(none)"
            previous_session_source = "recent_continuity" if previous_session_context != "(none)" else "none"
    else:
        previous_session_context = "(none)"

    just_now_context = render_recent_turns(just_now_turns, char_limit=recent_char_limit)
    scene_context = "\n".join(_render_memory(memory, 900) for memory in scene_memories) or "(none)"
    direct_seed_ids = [memory.id for memory in scene_memories]
    diffused_memories = diffuse_from_seed_ids(direct_seed_ids, max_items=3)
    diffused_context = render_diffused_context(diffused_memories)

    word_hints = {"used": False, "note": "Word Map prompt injection disabled; reserved for retrieval assistance.", "concepts": []}
    word_hint_context = "(none)"

    previous_context = get_last_injected_context()
    previous_ids = []
    for item in previous_context.get("scene_context", []) + previous_context.get("wake_context", []):
        memory_id = item.get("id")
        if memory_id:
            previous_ids.append(memory_id)

    detail_context = "(none)"
    if detail_requested and previous_ids:
        detail_context = detail_context_from_ids(previous_ids, max_items=3) or "(none)"

    messages = build_chat_messages(user_message, session_turns, recent_char_limit)

    injected = {
        "created_at": datetime.now().isoformat(),
        "session_id": _safe_session_id(session_id),
        "is_new_session": is_new_session,
        "recent_turns_count": recent_turns_count,
        "recent_char_limit": recent_char_limit,
        "message_history_count": len(session_turns),
        "user_message_preview": _truncate(user_message, 300),
        "profile_context_used": profile_context != "(none)",
        "previous_session_used": previous_session_context != "(none)",
        "previous_session_source": previous_session_source,
        "previous_session_id": previous_session_id,
        "previous_session_count": len(previous_session_turns),
        "relationship_weather_used": bool(weather_context and weather_context != "(none)"),
        "darkroom_door_used": bool(darkroom_context and darkroom_context != "(none)"),
        "wake_context": [_memory_ref(memory, "wake") for memory in wake_all[:2]],
        "just_now_used": bool(just_now_turns),
        "just_now_count": len(just_now_turns),
        "scene_context": [_memory_ref(memory, "scene") for memory in scene_memories],
        "diffused_context": diffused_memories,
        "word_map_hints": word_hints,
        "word_map_prompt_injection": False,
        "just_now_triggered": just_now_triggered,
        "detail_requested": detail_requested,
        "detail_recall_used": detail_context != "(none)",
        "detail_source_ids": previous_ids[:8] if detail_context != "(none)" else [],
        "direct_ids": direct_seed_ids,
        "wake_anchor_ids": [item["id"] for item in [_memory_ref(memory, "wake") for memory in wake_all[:2]]],
    }
    injected["layers"] = _context_layers(profile_context, weather_context, darkroom_context, wake_context, previous_session_context, just_now_turns, scene_memories, detail_context)
    for layer in injected["layers"]:
        if layer["name"] == "Graph Diffusion":
            layer["used"] = bool(diffused_memories)
            layer["count"] = len(diffused_memories)
        if layer["name"] == "Word Map Hints":
            layer["used"] = False
            layer["count"] = 0

    prompt = build_system_prompt(profile_context, weather_context, darkroom_context, wake_context, previous_session_context, just_now_context, scene_context, diffused_context, word_hint_context, detail_context)
    injected["prompt_preview"] = _truncate(prompt, 3000)
    LAST_CONTEXT_PATH.write_text(json.dumps(injected, ensure_ascii=False, indent=2), encoding="utf-8")

    return PreparedTurn(system_prompt=prompt, injected_context=injected, messages=messages)


async def consolidate_chat_turn(user_message: str, assistant_message: str, session_id: Optional[str] = None):
    record_chat_turn(user_message, assistant_message, session_id=session_id)
    profile_manager.update_recent_continuity(user_message, assistant_message)

    extraction = await extract_memory_from_conversation(user_message, assistant_message)
    memory = await save_extracted_memory(extraction)

    bucket_id = memory.id if memory else "conversation"
    title = extraction.get("name", "Conversation moment") if extraction else "Conversation moment"
    moment = create_moment(
        bucket_id=bucket_id,
        title=title,
        content=f"User: {user_message}\n\nKiro: {assistant_message}",
        tags=["conversation", "auto_moment"],
    )
    if memory:
        create_edge(memory.id, moment["id"], "continues", note="Conversation moment generated when this memory was consolidated.")

    return {"extraction": extraction, "memory_id": memory.id if memory else None, "moment_id": moment["id"]}


def get_last_injected_context() -> Dict:
    if not LAST_CONTEXT_PATH.exists():
        return {}
    try:
        return json.loads(LAST_CONTEXT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
