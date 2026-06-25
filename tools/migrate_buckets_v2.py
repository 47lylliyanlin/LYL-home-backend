"""
Migrate old memory buckets to Bucket v2 format.

Default mode is dry-run. Use --apply to write changes.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.bucket_format import is_bucket_v2, make_bucket_v2

MEMORY_DIR = ROOT / "memory"
TARGET_DIRS = [
    MEMORY_DIR / "permanent",
    MEMORY_DIR / "dynamic",
    MEMORY_DIR / "feel",
    MEMORY_DIR / "plans" / "active",
    MEMORY_DIR / "letters" / "history",
]


def split_frontmatter(text: str):
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return f"---{parts[1]}---\n", parts[2].lstrip()
    return "", text


def iter_bucket_files():
    for directory in TARGET_DIRS:
        if not directory.exists():
            continue
        yield from directory.rglob("*.md")


def migrate_file(path: Path, apply: bool = False) -> bool:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    if is_bucket_v2(body):
        return False

    title = path.stem
    migrated_body = make_bucket_v2(body, title=title)
    migrated_text = frontmatter + migrated_body

    if apply:
        path.write_text(migrated_text, encoding="utf-8")
    return True


def main():
    parser = argparse.ArgumentParser(description="Migrate memory buckets to Bucket v2 format.")
    parser.add_argument("--apply", action="store_true", help="Write migrated files. Omit for dry-run.")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N candidates.")
    args = parser.parse_args()

    candidates = []
    for path in iter_bucket_files():
        text = path.read_text(encoding="utf-8")
        _, body = split_frontmatter(text)
        if not is_bucket_v2(body):
            candidates.append(path)

    if args.limit:
        candidates = candidates[:args.limit]

    print(f"Bucket v2 migration {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Candidates: {len(candidates)}")

    changed = 0
    for path in candidates:
        changed_now = migrate_file(path, apply=args.apply)
        if changed_now:
            changed += 1
            print(f"[{'WRITE' if args.apply else 'WOULD'}] {path.relative_to(ROOT)}")

    print(f"Done. {'Migrated' if args.apply else 'Would migrate'}: {changed}")


if __name__ == "__main__":
    main()
