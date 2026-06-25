"""
Ombre Gateway for Kiro chat turns.

The Gateway prepares quiet memory context before the upstream model call,
then records the turn and asks the memory system to consolidate it after reply.
"""

import json
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
LAST_CONTEXT_PATH = RUNTIME_DIR / "last_injected_context.json"

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


def _ensure_runtime_dir():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


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


def load_recent_turns(limit: int = 10) -> List[Dict]:
    if not RECENT_TURNS_PATH.exists():
        return []

    turns = []
    for line in RECENT_TURNS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            turns.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return turns[-limit:]


def record_chat_turn(user_message: str, assistant_message: str):
    _ensure_runtime_dir()
    existing = load_recent_turns(limit=80)
    now = datetime.now().isoformat()
    existing.append({"role": "user", "content": user_message, "timestamp": now})
    existing.append({"role": "assistant", "content": assistant_message, "timestamp": now})
    existing = existing[-80:]
    RECENT_TURNS_PATH.write_text(
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


def render_recent_turns(turns: List[Dict]) -> str:
    if not turns:
        return "(none)"
    lines = []
    for item in turns:
        role = item.get("role", "unknown")
        content = _truncate(item.get("content", ""), 500)
        lines.append(f"- {role}: {content}")
    return "\n".join(lines)



def _context_layers(profile_context: str, weather_context: str, darkroom_context: str, wake_context: str, just_now_turns: List[Dict], scene_memories: List[Memory], detail_context: str) -> List[Dict]:
    return [
        {"name": "Profile Wake", "used": bool(profile_context), "count": 1, "role": "stable posture"},
        {"name": "Relationship Weather", "used": bool(weather_context and weather_context != "(none)"), "count": 1 if weather_context and weather_context != "(none)" else 0, "role": "tone"},
        {"name": "Darkroom Door", "used": bool(darkroom_context and darkroom_context != "(none)"), "count": 1 if darkroom_context and darkroom_context != "(none)" else 0, "role": "private-state signal"},
        {"name": "Wake Anchors", "used": wake_context != "(none)", "count": 0 if wake_context == "(none)" else wake_context.count("- id:"), "role": "optional anchor"},
        {"name": "Just Now", "used": bool(just_now_turns), "count": len(just_now_turns), "role": "recent chat"},
        {"name": "Scene Memory", "used": bool(scene_memories), "count": len(scene_memories), "role": "direct seed"},
        {"name": "Graph Diffusion", "used": False, "count": 0, "role": "low-confidence neighbor"},
        {"name": "Word Map Hints", "used": False, "count": 0, "role": "weak concept navigation"},
        {"name": "Detail Recall", "used": detail_context != "(none)", "count": 1 if detail_context != "(none)" else 0, "role": "follow-up detail"},
    ]


def build_system_prompt(profile_context: str, weather_context: str, darkroom_context: str, wake_context: str, just_now_context: str, scene_context: str, diffused_context: str, word_hint_context: str, detail_context: str) -> str:
    return f"""You are Kiro, talking with Bao Bao in a close, natural relationship.

Profile wake context: stable portraits and recent continuity.
{profile_context}

Relationship weather: shallow Dream Light summary.
{weather_context}

Darkroom door state: private internal reflection status only, never note contents.
{darkroom_context}

Optional wake anchors: a few reliable memories that help me wake up without noise.
{wake_context}

Just-now chat context: use this first for questions about what just happened.
{just_now_context}

Scene memory context: directly relevant memories for this turn.
{scene_context}

Diffused memory context: low-confidence graph neighbors. Use only as a light reminder after direct memory is relevant.
{diffused_context}

Word Map hints: weak concept navigation only, never evidence.
{word_hint_context}

Detail recall context: only use this when she asks to expand something already surfaced.
{detail_context}

Memory-use rules:
- Memory is background continuity. Use it to keep orientation, tone, promises, preferences, and relationship state coherent.
- Do not announce, summarize, prove, cite, or list injected memories unless Bao Bao directly asks what you remember.
- Do not begin replies by restating old memories. Answer the current message first.
- Do not say phrases like "according to memory", "the memory says", "I retrieved", or "I found in memory".
- If a memory only weakly relates, leave it silent. A natural reply is better than a complete memory report.
- Use wake/profile/weather context as posture, not content to quote.
- Use scene memory only when it changes the answer or prevents forgetting a relevant fact, promise, preference, or ongoing task.
- Use diffused memory only as low-confidence background after a direct seed is already relevant; never treat it as proof.
- Use Word Map hints only for navigation and theme awareness; never present them as remembered facts.
- For just-now questions, prefer the recent chat context over long-term memory.
- For detail-followup questions like "expand this" or "continue that", infer the referent from the latest chat turn first, then use Detail recall context if it helps.
- Do not ask which memory she means unless both recent chat and detail context are truly insufficient.
"""


def prepare_chat_turn(user_message: str) -> PreparedTurn:
    _ensure_runtime_dir()

    wake_memories = build_wake_memories()
    wake_all = _dedupe_memories(wake_memories)
    wake_ids = {memory.id for memory in wake_all}

    detail_requested = needs_detail_recall(user_message)
    just_now_turns = load_recent_turns(limit=10) if (needs_just_now_context(user_message) or detail_requested) else []
    scene_memories = [] if (just_now_turns or detail_requested) else build_scene_memories(user_message, exclude_ids=wake_ids)

    profile_context = profile_manager.build_wake_profile_context()
    weather_context = relationship_weather_context()
    darkroom_context = darkroom_door_context()
    wake_context = "\n".join(_render_memory(memory, 500) for memory in wake_all[:2]) or "(none)"
    just_now_context = render_recent_turns(just_now_turns)
    scene_context = "\n".join(_render_memory(memory, 900) for memory in scene_memories) or "(none)"
    direct_seed_ids = [memory.id for memory in scene_memories]
    diffused_memories = diffuse_from_seed_ids(direct_seed_ids, max_items=3)
    diffused_context = render_diffused_context(diffused_memories)
    word_hints = weak_concept_hints(user_message) if direct_seed_ids else {"used": False, "note": "No direct seed; Word Map skipped.", "concepts": []}
    word_hint_context = render_weak_concept_hints(word_hints)

    injected = {
        "created_at": datetime.now().isoformat(),
        "user_message_preview": _truncate(user_message, 300),
        "profile_context_used": True,
        "relationship_weather_used": bool(weather_context and weather_context != "(none)"),
        "darkroom_door_used": bool(darkroom_context and darkroom_context != "(none)"),
        "wake_context": [_memory_ref(memory, "wake") for memory in wake_all[:2]],
        "just_now_used": bool(just_now_turns),
        "just_now_count": len(just_now_turns),
        "scene_context": [_memory_ref(memory, "scene") for memory in scene_memories],
        "diffused_context": diffused_memories,
        "word_map_hints": word_hints,
        "just_now_triggered": needs_just_now_context(user_message),
        "detail_requested": detail_requested,
    }

    previous_context = get_last_injected_context()
    previous_ids = []
    for item in previous_context.get("scene_context", []) + previous_context.get("wake_context", []):
        memory_id = item.get("id")
        if memory_id:
            previous_ids.append(memory_id)

    detail_context = "(none)"
    if detail_requested and previous_ids:
        detail_context = detail_context_from_ids(previous_ids, max_items=3) or "(none)"

    injected["detail_recall_used"] = detail_context != "(none)"
    injected["detail_source_ids"] = previous_ids[:8] if injected["detail_recall_used"] else []
    injected["direct_ids"] = direct_seed_ids
    injected["wake_anchor_ids"] = [item["id"] for item in injected["wake_context"]]
    injected["layers"] = _context_layers(profile_context, weather_context, darkroom_context, wake_context, just_now_turns, scene_memories, detail_context)
    for layer in injected["layers"]:
        if layer["name"] == "Graph Diffusion":
            layer["used"] = bool(diffused_memories)
            layer["count"] = len(diffused_memories)
        if layer["name"] == "Word Map Hints":
            layer["used"] = bool(word_hints.get("concepts"))
            layer["count"] = len(word_hints.get("concepts", []))

    prompt = build_system_prompt(profile_context, weather_context, darkroom_context, wake_context, just_now_context, scene_context, diffused_context, word_hint_context, detail_context)
    injected["prompt_preview"] = _truncate(prompt, 3000)
    LAST_CONTEXT_PATH.write_text(json.dumps(injected, ensure_ascii=False, indent=2), encoding="utf-8")

    return PreparedTurn(system_prompt=prompt, injected_context=injected)


async def consolidate_chat_turn(user_message: str, assistant_message: str):
    record_chat_turn(user_message, assistant_message)
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
