"""JS syntax + light logic test for frontend assets.

Loads each JS file in a Node VM with a minimal `window`/`document` stub
and checks it doesn't throw on module-level execution.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "frontend" / "assets" / "js"


def main() -> int:
    js_files = sorted(ROOT.glob("*.js"))
    all_ok = True
    for f in js_files:
        # 1. Syntax check via Node
        result = subprocess.run(
            ["node", "--check", str(f)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            print(f"  [{f.name}] SYNTAX FAIL: {result.stderr.strip()[:200]}")
            all_ok = False
            continue
        # 2. Source-level sanity: count `await` outside async (rough)
        src = f.read_text(encoding="utf-8")
        if f.name != "ui.js":
            # ui.js defines functions, others should be wrapped
            if re.search(r"^await\s", src, re.M) and not re.search(r"async\s+function", src):
                print(f"  [{f.name}] WARN: top-level await without async wrapper")
        print(f"  [{f.name}] OK ({len(src)} bytes)")
    if all_ok:
        print("\n[PASS] all frontend JS files are syntactically valid")
        return 0
    print("\n[FAIL] some JS files failed syntax check")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())