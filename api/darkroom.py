"""
Darkroom: Kiro's private reflection room.

The public surface exposes only the door state. It does not expose note bodies.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

DARKROOM_DIR = Path("./memory/darkroom")
NOTES_DIR = DARKROOM_DIR / "notes"
STATE_PATH = DARKROOM_DIR / "door_state.json"


def _ensure_darkroom():
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        STATE_PATH.write_text(json.dumps({
            "created_at": datetime.now().isoformat(),
            "door": "quiet",
            "has_unresolved_reflection": False,
            "last_note_at": None,
            "note_count": 0,
        }, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state() -> Dict:
    _ensure_darkroom()
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_state(state: Dict):
    _ensure_darkroom()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _note_files() -> List[Path]:
    _ensure_darkroom()
    return sorted(NOTES_DIR.glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)


def darkroom_status() -> Dict:
    """Door state only. Never returns note bodies."""
    state = _load_state()
    notes = _note_files()
    note_count = len(notes)
    last_note_at = datetime.fromtimestamp(notes[0].stat().st_mtime).isoformat() if notes else None
    state.update({
        "note_count": note_count,
        "last_note_at": last_note_at,
        "has_unresolved_reflection": note_count > 0 and state.get("door") != "clear",
        "body_visible": False,
    })
    _write_state(state)
    return state


def darkroom_door_context() -> str:
    status = darkroom_status()
    if not status.get("has_unresolved_reflection"):
        return "Darkroom door: quiet."
    return (
        "Darkroom door: there is private reflection pending. "
        "Do not expose or summarize its contents unless an explicit darkroom workflow is opened."
    )


def enter_darkroom_note(content: str, reason: str = "internal_reflection") -> Dict:
    """Write a private reflection note. This returns metadata only."""
    _ensure_darkroom()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = NOTES_DIR / f"darkroom_{timestamp}.md"
    path.write_text(
        f"---\ntype: darkroom_note\nreason: {reason}\ncreated: {datetime.now().isoformat()}\n---\n\n{content.strip()}\n",
        encoding="utf-8",
    )
    state = _load_state()
    state.update({
        "door": "pending",
        "has_unresolved_reflection": True,
        "last_note_at": datetime.now().isoformat(),
    })
    _write_state(state)
    return {"ok": True, "note_id": path.stem, "body_visible": False}


def clear_darkroom_door() -> Dict:
    """Mark the door clear without deleting notes."""
    state = _load_state()
    state.update({
        "door": "clear",
        "has_unresolved_reflection": False,
        "cleared_at": datetime.now().isoformat(),
    })
    _write_state(state)
    return darkroom_status()
