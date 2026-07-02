"""
Pulse and introspection endpoints for the Kiro memory system.

Pulse is read-only. It does not mutate memory and does not call upstream models.
"""

from datetime import datetime
from typing import Dict

from .darkroom import darkroom_status
from .dream import dream_light_status
from .gateway import get_last_injected_context
from .memory import memory_system
from .memory_graph import graph_status
from .profile import profile_manager
from .word_map import load_word_map


def memory_counts() -> Dict[str, int]:
    counts = {
        "permanent": 0,
        "dynamic": 0,
        "feel": 0,
        "plan": 0,
        "letter": 0,
        "archive": 0,
        "total": 0,
    }
    memories = memory_system.load_all_memories(include_archive=True)
    for memory in memories:
        counts[memory.type] = counts.get(memory.type, 0) + 1
        counts["total"] += 1
    return counts


def pulse_status() -> Dict:
    word_map = load_word_map()
    dream = dream_light_status()
    darkroom = darkroom_status()
    graph = graph_status()
    last_context = get_last_injected_context()
    profiles = profile_manager.get_profiles()
    candidates = profile_manager.list_candidates()

    return {
        "generated_at": datetime.now().isoformat(),
        "memory_counts": memory_counts(),
        "gateway": {
            "has_last_context": bool(last_context),
            "last_context_at": last_context.get("created_at"),
            "profile_context_used": last_context.get("profile_context_used"),
            "relationship_weather_used": last_context.get("relationship_weather_used"),
            "darkroom_door_used": last_context.get("darkroom_door_used"),
            "just_now_used": last_context.get("just_now_used"),
            "detail_recall_used": last_context.get("detail_recall_used"),
            "scene_count": len(last_context.get("scene_context", [])),
            "wake_count": len(last_context.get("wake_context", [])),
            "tool_loop_enabled": last_context.get("tool_loop_enabled"),
            "tool_loop_requested": last_context.get("tool_loop_requested"),
            "tool_loop_tool": (last_context.get("tool_loop_request") or {}).get("tool"),
            "tool_loop_result_count": (last_context.get("tool_loop_result") or {}).get("count"),
        },
        "profile": {
            "documents": list(profiles.keys()),
            "candidate_count": len(candidates),
        },
        "graph": graph,
        "word_map": {
            "generated_at": word_map.get("generated_at"),
            "node_count": word_map.get("node_count"),
            "edge_count": word_map.get("edge_count"),
            "top_concepts": [item.get("word") for item in word_map.get("top_concepts", [])[:10]],
        },
        "dream_light": {
            "ran_at": dream.get("ran_at"),
            "relationship_weather": dream.get("relationship_weather"),
            "feel_count_sampled": dream.get("feel_count_sampled"),
        },
        "darkroom": {
            "door": darkroom.get("door"),
            "has_unresolved_reflection": darkroom.get("has_unresolved_reflection"),
            "note_count": darkroom.get("note_count"),
            "body_visible": False,
        },
    }


def introspection_status() -> Dict:
    pulse = pulse_status()
    return {
        "summary": {
            "memory_total": pulse["memory_counts"]["total"],
            "weather": pulse["dream_light"].get("relationship_weather"),
            "darkroom": pulse["darkroom"],
            "gateway_last_context_at": pulse["gateway"].get("last_context_at"),
        },
        "pulse": pulse,
        "notes": [
            "Pulse is read-only.",
            "Darkroom note bodies are not exposed.",
            "Word Map Lite is observational and not evidence.",
            "Profile candidates are not confirmed profile facts.",
        ],
    }
