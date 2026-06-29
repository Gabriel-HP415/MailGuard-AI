"""Fine-tune DistilBERT on the merged dataset."""

from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

from ai_service.app.config import settings
from ai_service.app.models.distilbert_classifier import build_training_dataset, train_distilbert
from ai_service.scripts.merge_datasets import merge_all

logger = logging.getLogger(__name__)


def _load_dataset(path: Path) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    labels: list[str] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            subj = row.get("subject", "")
            body = row.get("body", "")
            label = row.get("label", "")
            if not label or not body:
                continue
            texts.append(f"subject: {subj}\nbody: {body}")
            labels.append(label)
    return texts, labels


def train(epochs: int = 3, output_dir: Path | None = None) -> dict:
    """Train DistilBERT on the merged dataset. Returns training metrics."""
    dataset_path = settings.merged_dataset_path
    if not dataset_path.exists():
        logger.info("Merged dataset not found; merging sources...")
        merge_all()

    logger.info("Loading dataset from %s", dataset_path)
    texts, labels = _load_dataset(dataset_path)
    if not texts:
        raise RuntimeError("No training samples found in merged dataset.")

    train_ds, val_ds = build_training_dataset(texts, labels, val_split=0.2)
    out = output_dir or settings.models_dir / "distilbert_finetuned"
    metrics = train_distilbert(
        train_ds=train_ds,
        val_ds=val_ds,
        output_dir=out,
        epochs=epochs,
    )
    logger.info("DistilBERT training complete. Metrics: %s", metrics)
    return metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n_epochs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    m = train(epochs=n_epochs)
    print(f"DistilBERT training complete. Metrics: {m}")