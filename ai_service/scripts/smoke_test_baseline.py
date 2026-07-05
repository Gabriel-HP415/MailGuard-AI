"""Quick sanity test on the trained baseline SVM model.

Predicts against 4 hand-crafted emails (one per class). Useful as a
visual smoke test during model iteration.
"""

from __future__ import annotations

import logging
import pickle
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ai_service.app.preprocessing.text_cleaner import normalize_email  # noqa: E402
from ai_service.app.models.baselines import BaselineClassifier  # noqa: E402

logger = logging.getLogger("smoke_test")

SAMPLES = [
    (
        "normal",
        "Project update",
        "Hi team,\n\nI finished the Q3 deck. Latest numbers are attached. "
        "Please review before EOD Friday.\n\nThanks,\nLan",
    ),
    (
        "notification",
        "Your Amazon order has shipped",
        "Order #112-3390-99 has shipped via UPS. "
        "Estimated arrival: Wed, 9 Jul 2026. Track at amazon.com/track.",
    ),
    (
        "spam",
        "WIN A FREE iPHONE",
        "CONGRATULATIONS!!! You have been selected as the lucky winner of a brand new "
        "iPhone 16 Pro. Click here NOW to claim your prize before it expires. "
        "Limited time offer. 100% free. Act now!!!",
    ),
    (
        "scam",
        "URGENT: Your account has been suspended",
        "Dear customer, we detected unusual activity on your account. "
        "Verify your identity immediately to avoid suspension. Click here: "
        "http://secure-bank0famerica-verify.tk/login\n\nFailure to act within 24 hours "
        "will result in legal action and account termination.",
    ),
]


def main(model_path: str) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with open(model_path, "rb") as f:
        payload = pickle.load(f)
    clf = BaselineClassifier(algorithm=payload["algorithm"])
    clf.vectorizer_word = payload["vectorizer_word"]
    clf.vectorizer_char = payload["vectorizer_char"]
    clf.model = payload["model"]
    clf.classes_ = payload["classes_"]
    print("Loaded baseline model:", payload["algorithm"])
    print("Classes:", clf.classes_)
    print()

    texts = [normalize_email(subject=s, body=b) for _, s, b in SAMPLES]
    indices, probabilities = clf.predict(texts)

    rows = []
    for (expected_label, subj, body), idx, probs in zip(SAMPLES, indices, probabilities):
        pred_label = clf.classes_[int(idx)]
        conf = float(probs[int(idx)])
        all_probs = {clf.classes_[i]: float(p) for i, p in enumerate(probs)}
        ok = "OK" if pred_label == expected_label else "MISS"
        print(
            f"[{ok}] expected={expected_label:13s}  pred={pred_label:13s}  "
            f"conf={conf:.3f}  probs={all_probs}"
        )
        print(f"     subject: {subj[:60]}")
        rows.append((expected_label, pred_label, conf))

    matches = sum(1 for e, p, _ in rows if e == p)
    print()
    print(f"{matches}/{len(rows)} correct on this smoke test")
    return 0


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--model", default=str(
        PROJECT_ROOT / "ai_service" / "models" / "artifacts" / "baseline_svm.pkl"
    ))
    args = p.parse_args()
    raise SystemExit(main(args.model))
