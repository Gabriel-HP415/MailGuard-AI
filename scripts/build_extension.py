# ============================================
# MailGuard-AI — Build Extension Script
# ============================================
# Creates a zipped distributable for the Chrome Web Store.
# Usage:
#   python scripts/build_extension.py
# Output:
#   dist/mailguard-ai-extension-1.0.0.zip
# ============================================

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "chrome_extension"
DIST = ROOT / "dist"


def main() -> int:
    manifest_path = EXT / "manifest.json"
    if not manifest_path.exists():
        print(f"manifest.json not found at {manifest_path}", file=sys.stderr)
        return 1

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    version = manifest.get("version", "0.0.0")

    DIST.mkdir(parents=True, exist_ok=True)
    out = DIST / f"mailguard-ai-extension-{version}.zip"

    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in EXT.rglob("*"):
            if fp.is_dir():
                continue
            # Skip dev-only files
            if fp.name in {"README.md"} and fp.parent == EXT:
                # Keep root README for store info; skip dev-only docs elsewhere
                pass
            arcname = fp.relative_to(EXT).as_posix()
            zf.write(fp, arcname)

    print(f"Built: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())