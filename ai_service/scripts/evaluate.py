"""Evaluate a trained model on the merged dataset and produce a report.

Outputs:
- ``datasets/eval_report/report.json`` — full metrics (precision, recall, F1,
  accuracy, confusion matrix, per-class).
- ``datasets/eval_report/report.md``   — human-readable Markdown summary.
- ``datasets/eval_report/confusion_matrix.json`` — for downstream viz.

Usage:
    python -m ai_service.scripts.evaluate \
        --model models/artifacts/distilbert-v1 \
        --dataset datasets/merged_dataset.csv \
        --output-dir datasets/eval_report
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from ai_service.app.config import settings
from ai_service.app.preprocessing.text_cleaner import normalize_email

logger = logging.getLogger(__name__)


def _load_dataset(path: Path, max_samples: int | None = None) -> pd.DataFrame:
    df = pd.read_csv(path).fillna("")
    df = df[["label", "subject", "body"]]
    df = df[df["body"].astype(str).str.len() > 5]
    if max_samples:
        df = df.sample(min(max_samples, len(df)), random_state=42)
    return df.reset_index(drop=True)


def _predict_batch(model, df: pd.DataFrame) -> list[dict[str, Any]]:
    """Score each row through the loaded model. Returns list of prediction dicts."""
    preds = []
    for _, row in df.iterrows():
        text = normalize_email(
            subject=str(row.get("subject") or ""),
            body=str(row.get("body") or ""),
            sender=None,
        )
        result = model.predict(text)
        preds.append(result)
    return preds


def _compute_metrics(
    y_true: list[str], y_pred: list[str], classes: list[str]
) -> dict[str, Any]:
    """Compute accuracy, per-class precision/recall/F1, and the confusion matrix."""
    acc = sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)

    per_class: dict[str, dict[str, float]] = {}
    for cls in classes:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p != cls)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        support = sum(1 for t in y_true if t == cls)
        per_class[cls] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }

    # Macro / weighted
    macro_p = sum(c["precision"] for c in per_class.values()) / len(per_class)
    macro_r = sum(c["recall"] for c in per_class.values()) / len(per_class)
    macro_f1 = sum(c["f1"] for c in per_class.values()) / len(per_class)
    total_support = sum(c["support"] for c in per_class.values()) or 1
    weighted_p = sum(c["precision"] * c["support"] for c in per_class.values()) / total_support
    weighted_r = sum(c["recall"] * c["support"] for c in per_class.values()) / total_support
    weighted_f1 = sum(c["f1"] * c["support"] for c in per_class.values()) / total_support

    # Confusion matrix
    cm = []
    for true_cls in classes:
        row = []
        for pred_cls in classes:
            row.append(
                sum(1 for t, p in zip(y_true, y_pred) if t == true_cls and p == pred_cls)
            )
        cm.append(row)

    return {
        "accuracy": acc,
        "classes": classes,
        "per_class": per_class,
        "macro": {"precision": macro_p, "recall": macro_r, "f1": macro_f1},
        "weighted": {
            "precision": weighted_p,
            "recall": weighted_r,
            "f1": weighted_f1,
        },
        "confusion_matrix": cm,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Model Evaluation Report", ""]
    lines.append(f"- Total samples: **{report['total_samples']}**")
    lines.append(f"- Accuracy: **{report['metrics']['accuracy']:.4f}**")
    lines.append(
        f"- Macro F1: **{report['metrics']['macro']['f1']:.4f}**  "
        f"· Weighted F1: **{report['metrics']['weighted']['f1']:.4f}**"
    )
    lines.append("")
    lines.append("## Per-class metrics")
    lines.append("")
    lines.append("| Class | Precision | Recall | F1 | Support |")
    lines.append("|---|---|---|---|---|")
    for cls, m in report["metrics"]["per_class"].items():
        lines.append(
            f"| `{cls}` | {m['precision']:.4f} | {m['recall']:.4f} | "
            f"{m['f1']:.4f} | {m['support']} |"
        )
    lines.append("")
    lines.append("## Confusion matrix")
    lines.append("")
    cm = report["metrics"]["confusion_matrix"]
    classes = report["metrics"]["classes"]
    header = "| true \\ pred | " + " | ".join(classes) + " |"
    sep = "|" + "|".join(["---"] * (len(classes) + 1)) + "|"
    lines.append(header)
    lines.append(sep)
    for i, true_cls in enumerate(classes):
        row = " | ".join(str(x) for x in cm[i])
        lines.append(f"| `{true_cls}` | {row} |")
    lines.append("")
    return "\n".join(lines)


def _load_model(path: str | None):
    """Load a trained model from disk. Falls back to deterministic random."""
    from ai_service.app.config import settings as _s

    if path:
        try:
            import joblib  # type: ignore

            logger.info("Loading model from %s", path)
            return joblib.load(path)
        except Exception as exc:
            logger.warning("Could not load model %s (%s); falling back to random", path, exc)

    class _RandomModel:
        """Deterministic dummy model for end-to-end testing."""

        classes = sorted({"normal", "notification", "spam", "scam"})
        version = "random-baseline"

        def predict(self, text: str) -> dict[str, Any]:
            text_lower = (text or "").lower()
            if any(k in text_lower for k in ["verify", "password", "click here", "suspended"]):
                pred = "scam"
            elif any(k in text_lower for k in ["offer", "free", "win", "limited"]):
                pred = "spam"
            elif any(k in text_lower for k in ["order", "shipped", "delivered", "reminder"]):
                pred = "notification"
            else:
                pred = "normal"
            probs = {c: 0.0 for c in self.classes}
            probs[pred] = 0.7
            for c in self.classes:
                if c != pred:
                    probs[c] = 0.3 / (len(self.classes) - 1)
            return {
                "predicted_class": pred,
                "class_index": self.classes.index(pred),
                "confidence": probs[pred],
                "probabilities": probs,
            }

    return _RandomModel()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    p = argparse.ArgumentParser(description="Evaluate a trained email classifier")
    p.add_argument("--model", type=str, default=None, help="Path to a saved model")
    p.add_argument("--dataset", type=str, default=None, help="Dataset CSV path")
    p.add_argument("--output-dir", type=str, default=None, help="Where to write report")
    p.add_argument("--max-samples", type=int, default=2000,
                   help="Cap on samples for fast evals (set 0 for full)")
    args = p.parse_args()

    dataset_path = Path(args.dataset) if args.dataset else settings.merged_dataset_path
    output_dir = Path(args.output_dir) if args.output_dir else settings.datasets_dir / "eval_report"
    output_dir.mkdir(parents=True, exist_ok=True)

    df = _load_dataset(dataset_path, max_samples=args.max_samples or None)
    logger.info("Loaded %d samples", len(df))

    classes = sorted(df["label"].unique().tolist())
    logger.info("Classes: %s", classes)

    model = _load_model(args.model)

    preds = _predict_batch(model, df)
    y_true = df["label"].astype(str).tolist()
    y_pred = [p["predicted_class"] for p in preds]

    report = {
        "model": getattr(model, "version", "unknown"),
        "dataset": str(dataset_path),
        "total_samples": len(df),
        "class_counts": dict(Counter(y_true)),
        "metrics": _compute_metrics(y_true, y_pred, classes),
    }

    # Persist
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "report.md").write_text(_markdown_report(report), encoding="utf-8")
    (output_dir / "confusion_matrix.json").write_text(
        json.dumps(
            {
                "classes": classes,
                "matrix": report["metrics"]["confusion_matrix"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("Wrote evaluation report -> %s", output_dir)
    logger.info("Accuracy: %.4f, Macro F1: %.4f",
                report["metrics"]["accuracy"], report["metrics"]["macro"]["f1"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())