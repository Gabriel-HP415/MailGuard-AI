"""Generate MailGuard-AI extension icons.

Three sizes are required by manifest.json:
  - icons/icon16.png   (toolbar small)
  - icons/icon48.png   (extension management)
  - icons/icon128.png  (store listing)

The design is a simple shield with a gradient blue/violet background and
a white check mark, drawn programmatically with Pillow (PIL).

Usage:
    python scripts/generate_extension_icons.py

If Pillow is not installed:
    pip install Pillow
"""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Pillow is required. Install it with: pip install Pillow"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "chrome_extension" / "icons"
SIZES = (16, 48, 128)


def _gradient(size: int) -> Image.Image:
    """Vertical gradient from blue to indigo."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    top = (37, 99, 235, 255)      # #2563eb
    bottom = (99, 102, 241, 255)  # #6366f1
    for y in range(size):
        t = y / max(size - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        ImageDraw.Draw(img).line([(0, y), (size, y)], fill=(r, g, b, 255))
    return img


def _shield_mask(size: int) -> Image.Image:
    """White shield silhouette in the center of the canvas."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Filled rounded rectangle that morphs into a shield via a triangular bottom
    pad = max(1, int(size * 0.12))
    top_left = (pad, pad)
    bottom_right = (size - pad, size - pad)
    width = bottom_right[0] - top_left[0]
    height = bottom_right[1] - top_left[1]
    # Top half: rounded rectangle
    r = max(2, int(width * 0.18))
    upper_height = int(height * 0.6)
    upper_box = (top_left[0], top_left[1], bottom_right[0], top_left[1] + upper_height)
    draw.rounded_rectangle(upper_box, radius=r, fill=(255, 255, 255, 255))
    # Lower half: triangle pointing down to a single point
    apex_x = (top_left[0] + bottom_right[0]) // 2
    apex_y = bottom_right[1]
    draw.polygon(
        [
            (top_left[0], top_left[1] + upper_height - r),
            (bottom_right[0], top_left[1] + upper_height - r),
            (apex_x, apex_y),
        ],
        fill=(255, 255, 255, 255),
    )
    return img


def _check(size: int) -> Image.Image:
    """White check mark inside the shield, drawn last as a cutout-like overlay."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # The check mark is a thicker line — bezier approximation with two segments
    pad = max(4, int(size * 0.30))
    mid_x = size // 2
    mid_y = size // 2
    a = (pad, mid_y)
    b = (mid_x - max(1, int(size * 0.06)), mid_y + max(2, int(size * 0.18)))
    c = (size - pad, pad)
    width = max(2, size // 8)
    draw.line([a, b], fill=(37, 99, 235, 255), width=width)
    draw.line([b, c], fill=(37, 99, 235, 255), width=width)
    return img


def render(size: int) -> Image.Image:
    canvas = _gradient(size)
    shield = _shield_mask(size)
    canvas.alpha_composite(shield)
    check = _check(size)
    canvas.alpha_composite(check)
    return canvas


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        img = render(size)
        out = OUT_DIR / f"icon{size}.png"
        img.save(out, format="PNG", optimize=True)
        print(f"  {out} ({size}x{size}, {out.stat().st_size} bytes)")
    print(f"Icons generated in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())