"""
Dream Light: shallow memory digestion.

Dream Light updates relationship weather and a small dream state from safe,
non-private surfaces. It does not read Darkroom note bodies.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .darkroom import darkroom_status
from .memory import memory_system, rebuild_vector_index
from .memory_graph import graph_status
from .profile import profile_manager
from .word_map import load_word_map, rebuild_word_map

DREAM_DIR = Path("./memory/dream")
DREAM_STATE_PATH = DREAM_DIR / "dream_state.json"
RELATIONSHIP_WEATHER_PATH = DREAM_DIR / "relationship_weather.md"


def _ensure_dream_dir():
    DREAM_DIR.mkdir(parents=True, exist_ok=True)


def _truncate(text: str, limit: int = 400) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _recent_feel_memories(limit: int = 5) -> List[Dict]:
    memories = [memory for memory in memory_system.load_all_memories(include_archive=False) if memory.type == "feel"]
    memories.sort(key=lambda memory: memory.created, reverse=True)
    return [
        {
            "id": memory.id,
            "title": memory.name or memory.id,
            "valence": memory.valence,
            "arousal": memory.arousal,
            "preview": _truncate(memory.content, 240),
        }
        for memory in memories[:limit]
    ]


def _weather_from_inputs(recent_continuity: str, feels: List[Dict], darkroom: Dict) -> Dict:
    if darkroom.get("has_unresolved_reflection"):
        label = "private-reflection-pending"
        tone = "There is private reflection pending; stay gentle and do not expose it."
    elif feels:
        avg_valence = sum(item.get("valence", 0.5) for item in feels) / len(feels)
        avg_arousal = sum(item.get("arousal", 0.5) for item in feels) / len(feels)
        if avg_valence >= 0.65 and avg_arousal < 0.7:
            label = "warm-stable"
        elif avg_valence < 0.4:
            label = "tender-care-needed"
        elif avg_arousal >= 0.7:
            label = "active-intense"
        else:
            label = "present-and-working"
        tone = f"Recent affect valence={avg_valence:.2f}, arousal={avg_arousal:.2f}."
    elif "memory" in recent_continuity.lower() or "??" in recent_continuity:
        label = "focused-on-memory-system"
        tone = "The current continuity is centered on building and refining memory."
    else:
        label = "quiet"
        tone = "No strong relationship weather signal."
    return {"label": label, "tone": tone}


def run_dream_light() -> Dict:
    _ensure_dream_dir()
    profiles = profile_manager.get_profiles()
    recent_continuity = profiles.get("recent_continuity", "")
    feels = _recent_feel_memories()
    darkroom = darkroom_status()
    graph = graph_status()
    word_map = load_word_map()
    top_concepts = [item.get("word") for item in word_map.get("top_concepts", [])[:10]]
    weather = _weather_from_inputs(recent_continuity, feels, darkroom)

    weather_md = f"""# Relationship Weather

Last updated: {datetime.now().isoformat()}

## Weather

{weather['label']}

## Tone

{weather['tone']}

## Recent Continuity

{_truncate(recent_continuity, 1200)}

## Top Concepts

{', '.join(top_concepts) if top_concepts else 'none'}

## Darkroom Door

body_visible: false
has_unresolved_reflection: {darkroom.get('has_unresolved_reflection')}
"""
    RELATIONSHIP_WEATHER_PATH.write_text(weather_md, encoding="utf-8")

    state = {
        "ran_at": datetime.now().isoformat(),
        "mode": "light",
        "relationship_weather": weather,
        "feel_count_sampled": len(feels),
        "feel_samples": feels,
        "graph_status": graph,
        "top_concepts": top_concepts,
        "darkroom_door": {
            "has_unresolved_reflection": darkroom.get("has_unresolved_reflection"),
            "note_count": darkroom.get("note_count"),
            "body_visible": False,
        },
        "outputs": {
            "relationship_weather": str(RELATIONSHIP_WEATHER_PATH),
        },
    }
    DREAM_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def dream_light_status() -> Dict:
    if not DREAM_STATE_PATH.exists():
        return run_dream_light()
    try:
        return json.loads(DREAM_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return run_dream_light()


def relationship_weather_context() -> str:
    status = dream_light_status()
    weather = status.get("relationship_weather", {})
    return f"Relationship weather: {weather.get('label', 'unknown')} - {weather.get('tone', '')}"


def run_memory_maintenance() -> Dict:
    """Run safe maintenance surfaces without exposing Darkroom note bodies."""
    vector = rebuild_vector_index(include_archive=False)
    word_map = rebuild_word_map()
    dream = run_dream_light()
    graph = graph_status()
    darkroom = darkroom_status()
    return {
        "ran_at": datetime.now().isoformat(),
        "tasks": {
            "vector_index_rebuilt": True,
            "word_map_rebuilt": True,
            "dream_light_ran": True,
            "darkroom_body_read": False,
        },
        "vector_index": vector,
        "word_map": {
            "generated_at": word_map.get("generated_at"),
            "node_count": word_map.get("node_count"),
            "edge_count": word_map.get("edge_count"),
        },
        "dream_light": {
            "ran_at": dream.get("ran_at"),
            "relationship_weather": dream.get("relationship_weather"),
        },
        "graph": graph,
        "darkroom": {
            "door": darkroom.get("door"),
            "has_unresolved_reflection": darkroom.get("has_unresolved_reflection"),
            "note_count": darkroom.get("note_count"),
            "body_visible": False,
        },
    }
