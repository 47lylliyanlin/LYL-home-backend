"""
Bucket v2 format helpers.

Bucket v2 separates reliable factual material from interpretation and warmth.
Direct recall should prefer Fact and Evidence, while Temperature is only auxiliary.
"""

from dataclasses import dataclass
from typing import Dict, List

V2_MARKER = "bucket_format: v2"
SECTIONS = [
    "Fact",
    "Evidence",
    "My Understanding",
    "Promise / Next",
    "Temperature",
    "Original",
]
DIRECT_SEED_SECTIONS = {"Fact", "Evidence", "Promise / Next"}
AUXILIARY_SECTIONS = {"My Understanding", "Temperature"}


@dataclass
class BucketV2:
    title: str
    sections: Dict[str, str]


def is_bucket_v2(content: str) -> bool:
    return V2_MARKER in content or "## Fact" in content and "## Evidence" in content


def _title_from_content(content: str, fallback: str = "Untitled Bucket") -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.lstrip("#").strip() or fallback
    return fallback


def _clean(text: str) -> str:
    return (text or "").strip()


def split_v2_sections(content: str) -> BucketV2:
    title = _title_from_content(content)
    sections = {name: "" for name in SECTIONS}
    current = None
    buffer: List[str] = []

    def flush():
        nonlocal buffer, current
        if current:
            sections[current] = _clean("\n".join(buffer))
        buffer = []

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped[3:].strip()
            if heading in sections:
                flush()
                current = heading
                continue
        if current:
            buffer.append(line)
    flush()

    return BucketV2(title=title, sections=sections)


def make_bucket_v2(content: str, title: str = "") -> str:
    if is_bucket_v2(content):
        return content

    inferred_title = title or _title_from_content(content)
    original = _clean(content)
    fact = "This bucket was migrated from an older memory format. Treat the Original section as source material until reviewed."
    evidence = "Pending manual review. Original text is preserved below."

    return f"""---
{V2_MARKER}
---

# {inferred_title}

## Fact

{fact}

## Evidence

{evidence}

## My Understanding

Pending review.

## Promise / Next

None recorded.

## Temperature

None recorded.

## Original

{original}
""".strip() + "\n"


def direct_seed_text(content: str) -> str:
    if not is_bucket_v2(content):
        return content

    parsed = split_v2_sections(content)
    parts = []
    for name in SECTIONS:
        if name in DIRECT_SEED_SECTIONS and parsed.sections.get(name):
            parts.append(f"## {name}\n{parsed.sections[name]}")
    return "\n\n".join(parts).strip() or content


def auxiliary_text(content: str) -> str:
    if not is_bucket_v2(content):
        return ""

    parsed = split_v2_sections(content)
    parts = []
    for name in SECTIONS:
        if name in AUXILIARY_SECTIONS and parsed.sections.get(name):
            parts.append(f"## {name}\n{parsed.sections[name]}")
    return "\n\n".join(parts).strip()
