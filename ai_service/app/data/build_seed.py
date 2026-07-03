"""Build a small, ready-to-train CSV from the in-repo seed data.

Used as the *last* fallback in `merge_all()` so the AI service can always
train a baseline classifier on first boot even when every public dataset
download fails (offline deploys, CI sandboxes behind a strict proxy).

The resulting CSV has the same schema as ``merged_dataset.csv``:
``label, subject, body, source``. Rows are slightly augmented by emitting
each seed sample twice with shuffled word order inside the body — the
distortion is small enough to keep labels realistic while doubling the
training-set size.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

from ai_service.app.config import settings
from ai_service.app.data.seed_dataset import SEED_ROWS


def _shuffle_words(text: str, rng: random.Random) -> str:
    """Return a copy of ``text`` with words in random order.

    Keeps punctuation placement roughly stable. Helps the trained model
    not over-fit to a single sentence structure.
    """
    words = text.split()
    if len(words) < 6:
        return text
    rng.shuffle(words)
    return " ".join(words)


def build_seed_csv(out_path: Path | None = None, *, augment: bool = True) -> Path:
    """Write the seed dataset to disk and return the path."""
    out_path = out_path or settings.merged_dataset_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(settings.random_seed)
    rows: list[tuple[str, str, str, str]] = []
    for label, subject, body in SEED_ROWS:
        rows.append((label, subject, body, "seed"))
        if augment:
            rows.append((label, subject, _shuffle_words(body, rng), "seed_aug"))

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["label", "subject", "body", "source"])
        for row in rows:
            writer.writerow(row)

    by_class: dict[str, int] = {}
    for r in rows:
        by_class[r[0]] = by_class.get(r[0], 0) + 1
    return out_path


if __name__ == "__main__":
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Build the seed dataset CSV")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--no-augment", action="store_true")
    args = parser.parse_args()

    p = build_seed_csv(args.out, augment=not args.no_augment)
    print(f"Wrote {p}")
