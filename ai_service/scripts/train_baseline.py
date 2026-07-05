"""Train a baseline model (Naive Bayes, SVM, or Random Forest) and save it.

After training, this script can optionally:
  1. Run the evaluation pipeline (writes ``datasets/eval_report/*``).
  2. Publish the model version to the backend admin API.

Usage:
    python -m ai_service.scripts.train_baseline naive_bayes \\
        --evaluate \\
        --publish --version v1.0.0 \\
        --admin-email admin@mailguard.ai \\
        --admin-password secret --activate
"""

from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

from ai_service.app.config import settings
from ai_service.app.models.baselines import BaselineClassifier, BaselineMetrics
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
            texts.append(f"{subj}\n{body}")
            labels.append(label)
    return texts, labels


def _augment_minority_classes(texts: list[str], labels: list[str], multiplier: int = 2) -> tuple[list[str], list[str]]:
    """Apply data augmentation to scam / spam classes."""
    from ai_service.app.preprocessing.augment import augment_dataset

    triples = augment_dataset(
        zip(labels, [""] * len(texts), texts),
        target_classes=("scam", "spam"),
        multiplier=multiplier,
    )
    new_labels = [t[0] for t in triples]
    new_texts = [t[2] for t in triples]
    return new_texts, new_labels


def train_and_save(
    algorithm: str = "naive_bayes",
    dataset_path: Path | None = None,
    augment: bool = False,
) -> tuple[Path, BaselineMetrics | None]:
    """Train a baseline classifier and persist the artifact. Returns (path, metrics)."""
    if dataset_path is None:
        dataset_path = settings.merged_dataset_path
    if not dataset_path.exists():
        logger.info("Merged dataset not found; merging sources...")
        merge_all()

    logger.info("Loading dataset from %s", dataset_path)
    texts, labels = _load_dataset(dataset_path)
    if not texts:
        raise RuntimeError("No training samples found in merged dataset.")
    logger.info(
        "Class distribution before augmentation: %s",
        {k: labels.count(k) for k in set(labels)},
    )

    if augment:
        before = len(texts)
        # Increase minority classes more aggressively: scam is naturally the
        # smallest class (Phishing_Email.csv only labels phishing-or-safe, no
        # extra scam data). Spam is bigger but worth oversampling to balance
        # the heavy "normal" majority.
        texts, labels = _augment_minority_classes(texts, labels, multiplier=4)
        logger.info("Data augmentation grew dataset from %d to %d rows", before, len(texts))

    clf = BaselineClassifier(algorithm=algorithm)
    metrics: BaselineMetrics | None = clf.fit(texts, labels, eval_split=True)
    if metrics:
        logger.info(
            "Baseline %s | acc=%.4f prec=%.4f rec=%.4f f1=%.4f",
            algorithm, metrics.accuracy, metrics.precision, metrics.recall, metrics.f1,
        )

    out = settings.models_dir / f"baseline_{algorithm}.pkl"
    clf.save(out)
    return out, metrics


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Train an email baseline classifier")
    p.add_argument("algorithm", nargs="?", default="naive_bayes",
                   choices=["naive_bayes", "svm", "random_forest", "logistic_regression"])
    p.add_argument("--augment", action="store_true",
                   help="Augment minority classes (scam, spam) before training")
    p.add_argument("--evaluate", action="store_true",
                   help="Run the evaluation pipeline after training")
    p.add_argument("--publish", action="store_true",
                   help="Publish the resulting model version to the backend")
    p.add_argument("--version", default=None, help="Version string for publish")
    p.add_argument("--admin-email", default=None)
    p.add_argument("--admin-password", default=None)
    p.add_argument("--backend-url", default=None)
    p.add_argument("--activate", action="store_true")
    args = p.parse_args()

    model_path, metrics = train_and_save(
        algorithm=args.algorithm,
        augment=args.augment,
    )
    print(f"Saved model to: {model_path}")

    accuracy = metrics.accuracy if metrics else 0.0

    if args.evaluate:
        from ai_service.scripts.evaluate import main as evaluate_main
        logger.info("Running evaluation pipeline...")
        evaluate_main()  # uses defaults

    if args.publish:
        if not args.version:
            raise SystemExit("--version is required when --publish is set")
        from ai_service.scripts.publish_model import publish
        result = publish(
            version=args.version,
            algorithm=args.algorithm if args.algorithm != "naive_bayes" else "naive_bayes",
            accuracy=accuracy,
            artifact_path=str(model_path),
            description=f"Baseline {args.algorithm}"
                        + (" + augmented" if args.augment else ""),
            backend_url=args.backend_url,
            admin_email=args.admin_email,
            admin_password=args.admin_password,
            activate=args.activate,
            force=True,
        )
        print("Published:", result)

    sys.exit(0)