"""Download the vendored CSS/JS assets used by the frontend."""

from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS_DIR = ROOT / "frontend" / "assets" / "css"
JS_DIR = ROOT / "frontend" / "assets" / "vendor"
CSS_DIR.mkdir(parents=True, exist_ok=True)
JS_DIR.mkdir(parents=True, exist_ok=True)

ASSETS = [
    (
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
        CSS_DIR / "bootstrap.min.css",
    ),
    (
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
        JS_DIR / "bootstrap.bundle.min.js",
    ),
    (
        "https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js",
        JS_DIR / "chart.umd.min.js",
    ),
]


def main() -> int:
    for url, dest in ASSETS:
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"Already have {dest.name} ({dest.stat().st_size} bytes) — skipping")
            continue
        print(f"Downloading {url} -> {dest}")
        req = urllib.request.Request(
            url, headers={"User-Agent": "MailGuard-AI/1.0 (+https://mailguard.ai)"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        dest.write_bytes(data)
        print(f"  {dest} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())