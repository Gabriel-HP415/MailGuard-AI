"""A minimal stubbed training set for fast unit tests of BaselineClassifier."""

from __future__ import annotations

import os
import pickle
import tempfile

from ai_service.app.models.baselines import BaselineClassifier


def test_baseline_trains_and_predicts():
    texts = [
        "win a free iphone click here now",
        "verify your account immediately",
        "wire transfer lottery winner claim your prize",
        "your order has shipped",
        "meeting reminder weekly sync",
        "lunch on friday?",
        "attached is the project report",
        "let's grab coffee tomorrow",
    ]
    labels = ["spam", "scam", "scam", "notification", "notification", "normal", "normal", "normal"]
    clf = BaselineClassifier(algorithm="naive_bayes")
    metrics = clf.fit(texts, labels, eval_split=True)
    assert metrics is not None
    preds, probs = clf.predict(texts)
    assert len(preds) == len(texts)
    assert probs.shape[0] == len(texts)
    assert probs.shape[1] == 4

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test_nb.pkl")
        clf.save(__import__("pathlib").Path(path))
        loaded = BaselineClassifier.load(__import__("pathlib").Path(path))
        preds2, probs2 = loaded.predict(texts)
        assert list(preds2) == list(preds)
        assert probs2.shape == probs.shape