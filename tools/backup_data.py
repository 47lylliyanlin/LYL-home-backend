"""Create a local backup archive for Kiro runtime data.

Backs up memory/, runtime/, and chroma_db/ by default. The real .env file is
intentionally excluded. Store the resulting zip somewhere private.
"""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ITEMS = ["memory", "runtime", "chroma_db"]
EXCLUDED_NAMES = {".env", "*.log"}


def should_skip(path: Path) -> bool:
    name = path.name.lower()
    if name == ".env" or name.endswith(".log"):
        return True
    if "audio" in [part.lower() for part in path.parts]:
        return True
    return False


def add_path(zf: zipfile.ZipFile, path: Path, root: Path) -> int:
    count = 0
    if not path.exists():
        return 0
    if path.is_file():
        if not should_skip(path):
            zf.write(path, path.relative_to(root).as_posix())
            count += 1
        return count
    for item in path.rglob("*"):
        if item.is_file() and not should_skip(item):
            zf.write(item, item.relative_to(root).as_posix())
            count += 1
    return count


def create_backup(output_dir: Path, include_chroma: bool = True) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive = output_dir / f"kiro_backup_{timestamp}.zip"
    items = list(DEFAULT_ITEMS)
    if not include_chroma and "chroma_db" in items:
        items.remove("chroma_db")

    manifest = {
        "created_at": datetime.now().isoformat(),
        "root": str(ROOT),
        "items": items,
        "env_included": False,
    }

    file_count = 0
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            file_count += add_path(zf, ROOT / item, ROOT)
        zf.writestr("backup_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    print(f"[OK] backup created: {archive}")
    print(f"[OK] files archived: {file_count}")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Kiro memory/runtime backup archive.")
    parser.add_argument("--output", default=os.getenv("KIRO_BACKUP_DIR", str(ROOT / "backups")), help="Backup output directory.")
    parser.add_argument("--no-chroma", action="store_true", help="Exclude chroma_db from backup.")
    args = parser.parse_args()
    create_backup(Path(args.output), include_chroma=not args.no_chroma)


if __name__ == "__main__":
    main()
