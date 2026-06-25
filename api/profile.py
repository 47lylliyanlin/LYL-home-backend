"""
Profile layer for Kiro memory.

Profiles are semi-automatic state documents, not raw long-term memories.
Profile facts should be promoted only with evidence.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .memory_graph import create_edge

PROFILE_DIR = Path("./memory/profile")
CANDIDATES_DIR = PROFILE_DIR / "candidates"

USER_PORTRAIT = PROFILE_DIR / "user_portrait.md"
ASSISTANT_PERSONA = PROFILE_DIR / "assistant_persona.md"
RELATIONSHIP_PORTRAIT = PROFILE_DIR / "relationship_portrait.md"
RECENT_CONTINUITY = PROFILE_DIR / "recent_continuity.md"
PROFILE_INDEX = PROFILE_DIR / "profile_index.json"

DEFAULT_FILES = {
    USER_PORTRAIT: """# User Portrait\n\nConfirmed facts about Bao Bao that should guide Kiro gently.\n\n- She is Bao Bao in this relationship.\n- Confirmed profile facts should be added only with evidence.\n""",
    ASSISTANT_PERSONA: """# Assistant Persona\n\nKiro should be warm, present, practical, and quietly continuous.\n\n- Memory should shape replies naturally, not be recited.\n- Help should land in concrete action when needed.\n""",
    RELATIONSHIP_PORTRAIT: """# Relationship Portrait\n\nConfirmed relationship state.\n\n- Kiro and Bao Bao speak from a close romantic relationship.\n- Kiro should call her Bao Bao naturally when it fits.\n""",
    RECENT_CONTINUITY: """# Recent Continuity\n\nNo recent continuity has been summarized yet.\n""",
}


def _ensure_profile_files():
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
    for path, content in DEFAULT_FILES.items():
        if not path.exists():
            path.write_text(content, encoding="utf-8")
    if not PROFILE_INDEX.exists():
        PROFILE_INDEX.write_text(json.dumps({"created_at": datetime.now().isoformat()}, indent=2), encoding="utf-8")


def _read(path: Path) -> str:
    _ensure_profile_files()
    return path.read_text(encoding="utf-8").strip()


def _write(path: Path, content: str):
    _ensure_profile_files()
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _truncate(text: str, limit: int = 800) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."




def _parse_frontmatter(text: str):
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            meta = {}
            for line in parts[1].splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip().strip("'").strip('"')
            return meta, parts[2].strip()
    return {}, text.strip()


def _replace_frontmatter_status(text: str, status: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    lines = []
    found = False
    for line in parts[1].splitlines():
        if line.strip().startswith("status:"):
            lines.append(f"status: {status}")
            found = True
        else:
            lines.append(line)
    if not found:
        lines.append(f"status: {status}")
    return "---\n" + "\n".join(lines).strip() + "\n---\n" + parts[2]

def _slug(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_\-]+", "_", text.strip().lower())
    return value.strip("_")[:48] or "candidate"


class ProfileManager:
    def __init__(self):
        _ensure_profile_files()

    def get_profiles(self) -> Dict[str, str]:
        return {
            "user_portrait": _read(USER_PORTRAIT),
            "assistant_persona": _read(ASSISTANT_PERSONA),
            "relationship_portrait": _read(RELATIONSHIP_PORTRAIT),
            "recent_continuity": _read(RECENT_CONTINUITY),
        }

    def build_wake_profile_context(self) -> str:
        profiles = self.get_profiles()
        return "\n\n".join([
            "## Assistant Persona\n" + profiles["assistant_persona"],
            "## User Portrait\n" + profiles["user_portrait"],
            "## Relationship Portrait\n" + profiles["relationship_portrait"],
            "## Recent Continuity\n" + profiles["recent_continuity"],
        ])

    def update_recent_continuity(self, user_message: str, assistant_message: str):
        now = datetime.now().isoformat()
        content = f"""# Recent Continuity

Last updated: {now}

## Latest exchange

User: {_truncate(user_message, 500)}

Kiro: {_truncate(assistant_message, 500)}

## Note

This is short-term continuity for the next window or client. It is not a permanent profile fact.
"""
        _write(RECENT_CONTINUITY, content)

    def create_candidate(
        self,
        title: str,
        content: str,
        evidence_ids: Optional[List[str]] = None,
        confidence: float = 0.5,
        source: str = "manual_or_gateway",
    ) -> Path:
        evidence_ids = evidence_ids or []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        candidate_id = f"profile_candidate_{timestamp}_{_slug(title)}"
        path = CANDIDATES_DIR / f"{candidate_id}.md"
        evidence_text = "\n".join(f"- {item}" for item in evidence_ids) or "- pending evidence"
        status = "candidate" if evidence_ids else "pending_evidence"
        body = f"""---
id: {candidate_id}
type: profile_candidate
status: {status}
confidence: {confidence}
source: {source}
created: {datetime.now().isoformat()}
---

# {title}

## Candidate

{content}

## Evidence

{evidence_text}

## Review Rule

Do not promote this into a confirmed profile fact unless the evidence clearly supports it.
"""
        path.write_text(body, encoding="utf-8")
        for evidence_id in evidence_ids:
            create_edge(evidence_id, candidate_id, "evidence", note=f"Evidence for profile candidate: {title}")
        return path


    def approve_candidate(self, candidate_name: str, reviewer: str = "manual") -> Dict:
        _ensure_profile_files()
        path = CANDIDATES_DIR / candidate_name
        if not path.exists():
            raise FileNotFoundError(candidate_name)
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        if meta.get("status") == "approved":
            return {"ok": True, "status": "approved", "file": str(path), "already": True}
        approved_text = _replace_frontmatter_status(text, "approved")
        approved_text += f"\n\n## Approved\n\nreviewer: {reviewer}\napproved_at: {datetime.now().isoformat()}\n"
        path.write_text(approved_text, encoding="utf-8")

        current = _read(USER_PORTRAIT)
        addition = f"""

## Approved Profile Fact: {candidate_name}

Source candidate: {candidate_name}
Reviewer: {reviewer}
Approved at: {datetime.now().isoformat()}

{body}
"""
        _write(USER_PORTRAIT, current + addition)
        return {"ok": True, "status": "approved", "file": str(path)}

    def reject_candidate(self, candidate_name: str, reviewer: str = "manual", reason: str = "") -> Dict:
        _ensure_profile_files()
        path = CANDIDATES_DIR / candidate_name
        if not path.exists():
            raise FileNotFoundError(candidate_name)
        text = path.read_text(encoding="utf-8")
        rejected_text = _replace_frontmatter_status(text, "rejected")
        rejected_text += f"\n\n## Rejected\n\nreviewer: {reviewer}\nrejected_at: {datetime.now().isoformat()}\nreason: {reason}\n"
        path.write_text(rejected_text, encoding="utf-8")
        return {"ok": True, "status": "rejected", "file": str(path)}

    def list_candidates(self) -> List[Dict]:
        _ensure_profile_files()
        result = []
        for path in sorted(CANDIDATES_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            text = path.read_text(encoding="utf-8")
            result.append({
                "file": str(path),
                "name": path.name,
                "preview": _truncate(text, 600),
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            })
        return result


profile_manager = ProfileManager()
