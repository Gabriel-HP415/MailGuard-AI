"""Evaluate a baseline (NB/SVM/RF) model saved with `pickle`.

The default ai_service.scripts.evaluate expects a joblib-saved model with
a `.predict(text)` method. Our `BaselineClassifier` is pickled and exposes
`predict([list_of_texts])`. This shim bridges the two interfaces so we
can score the trained model against the merged dataset.
"""

from __future__ import annotations

import logging
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ai_service.app.config import settings  # noqa: E402
from ai_service.app.preprocessing.text_cleaner import normalize_email  # noqa: E402

logger = logging.getLogger("eval_baseline")


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--dataset", default=str(settings.merged_dataset_path))
    p.add_argument("--max-samples", type=int, default=2000)
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    model_path = Path(args.model)
    logger.info("Loading baseline model: %s", model_path)
    with open(model_path, "rb") as f:
        payload = pickle.load(f)
    classes = payload["classes_"]

    def _classify(text: str) -> dict:
        preds, probs = payload["model"].transform_later  # placeholder, replaced below
        return None

    import pandas as pd

    df = pd.read_csv(args.dataset).fillna("")
    df = df[df["body"].astype(str).str.len() > 5]
    if args.max_samples and len(df) > args.max_samples:
        # Stratified sub-sample so we always include representatives of every
        # class — random sampling tends to miss the rare ``scam`` rows.
        from sklearn.model_selection import train_test_split
        df, _ = train_test_split(
            df,
            train_size=min(args.max_samples, len(df)),
            stratify=df["label"],
            random_state=42,
        )
    df = df.reset_index(drop=True)
    logger.info("Loaded %d rows", len(df))
    logger.info("Class distribution: %s", df["label"].value_counts().to_dict())

    texts = [
        normalize_email(subject=str(r.get("subject") or ""), body=str(r.get("body") or ""))
        for _, r in df.iterrows()
    ]

    # BaselineClassifier exposes predict(); use the same wrapper the publish
    # script uses so we don't have to re-implement its vectorization.
    from ai_service.app.models.baselines import BaselineClassifier  # noqa: E402

    # Hack: rebuild the classifier then overlay the persisted pieces.
    clf = BaselineClassifier(algorithm=payload["algorithm"])
    clf.vectorizer_word = payload["vectorizer_word"]
    clf.vectorizer_char = payload["vectorizer_char"]
    clf.model = payload["model"]
    clf.classes_ = payload["classes_"]

    indices, probabilities = clf.predict(texts)
    y_pred = [classes[int(i)] for i in indices]
    y_true = df["label"].astype(str).tolist()

    correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    acc = correct / len(y_true)
    per_class: dict[str, dict] = {}
    for cls in classes:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p != cls)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        support = sum(1 for t in y_true if t == cls)
        per_class[cls] = {"precision": prec, "recall": rec, "f1": f1, "support": support}

    macro_p = sum(c["precision"] for c in per_class.values()) / len(per_class)
    macro_r = sum(c["recall"] for c in per_class.values()) / len(per_class)
    macro_f1 = sum(c["f1"] for c in per_class.values()) / len(per_class)

    cm = []
    for tc in classes:
        row = [sum(1 for t, p in zip(y_true, y_pred) if t == tc and p == pc) for pc in classes]
        cm.append(row)

    # Write report
    out_dir = settings.datasets_dir / "eval_report"
    out_dir.mkdir(parents=True, exist_ok=True)
    import json

    report = {
        "model": f"baseline_{payload['algorithm']}",
        "dataset": args.dataset,
        "total_samples": len(y_true),
        "class_counts": {c: sum(1 for t in y_true if t == c) for c in classes},
        "metrics": {
            "accuracy": acc,
            "classes": classes,
            "per_class": per_class,
            "macro": {"precision": macro_p, "recall": macro_r, "f1": macro_f1},
            "weighted": {},
            "confusion_matrix": cm,
        },
    }
    (out_dir / "baseline_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    # Markdown summary
    lines = [
        f"# Baseline {payload['algorithm']} Evaluation",
        f"- Samples: {len(y_true)}",
        f"- Accuracy: **{acc:.4f}**",
        f"- Macro F1: **{macro_f1:.4f}**",
        "",
        "## Per-class",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---|---|---|---|",
    ]
    for cls, m in per_class.items():
        lines.append(
            f"| `{cls}` | {m['precision']:.4f} | {m['recall']:.4f} | "
            f"{m['f1']:.4f} | {m['support']} |"
        )
    lines.append("")
    lines.append("## Confusion matrix")
    lines.append("| true \\ pred | " + " | ".join(classes) + " |")
    lines.append("|" + "|".join(["---"] * (len(classes) + 1)) + "|")
    for i, tc in enumerate(classes):
        lines.append("| `" + tc + "` | " + " | ".join(str(x) for x in cm[i]) + " |")
    (out_dir / "baseline_report.md").write_text("\n".join(lines), encoding="utf-8")

    logger.info(
        "Baseline %s | acc=%.4f macro_f1=%.4f",
        payload["algorithm"], acc, macro_f1,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
