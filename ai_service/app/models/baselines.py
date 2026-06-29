"""Baseline ML models (Naive Bayes, SVM, Random Forest) with TF-IDF."""

from __future__ import annotations

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.sparse import hstack
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from ai_service.app.config import settings
from ai_service.app.constants import CLASS_TO_INDEX, EmailClass
from ai_service.app.preprocessing.text_cleaner import clean_text

logger = logging.getLogger(__name__)


@dataclass
class BaselineMetrics:
    """Performance metrics for a baseline model."""

    accuracy: float
    precision: float
    recall: float
    f1: float


class BaselineClassifier:
    """A unified wrapper for NB / SVM / Random Forest + TF-IDF."""

    def __init__(self, algorithm: str = "naive_bayes"):
        if algorithm not in {"naive_bayes", "svm", "random_forest"}:
            raise ValueError(f"Unknown baseline algorithm: {algorithm}")
        self.algorithm = algorithm
        self.vectorizer_word = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True,
        )
        self.vectorizer_char = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=2,
            sublinear_tf=True,
        )
        self.model = self._build_model(algorithm)
        self.classes_: list[str] = []

    @staticmethod
    def _build_model(algorithm: str):
        if algorithm == "naive_bayes":
            return MultinomialNB(alpha=0.1)
        if algorithm == "svm":
            return CalibratedClassifierCV(LinearSVC(C=1.0), cv=3)
        return RandomForestClassifier(
            n_estimators=200,
            n_jobs=-1,
            random_state=settings.random_seed,
        )

    @staticmethod
    def _vectorize(
        vectorizers: list[TfidfVectorizer], texts: list[str]
    ):
        mats = [v.transform(texts) for v in vectorizers]
        if len(mats) == 1:
            return mats[0]
        return hstack(mats, format="csr")

    def fit(
        self,
        texts: Iterable[str],
        labels: Iterable[str | int],
        eval_split: bool = True,
    ) -> BaselineMetrics | None:
        """Fit the model. Optionally returns metrics on a holdout split."""
        texts = [clean_text(t) for t in texts]
        labels = list(labels)
        y = np.array(
            [CLASS_TO_INDEX[EmailClass(l)] if isinstance(l, str) else int(l) for l in labels]
        )

        if eval_split:
            tx, vx, ty, vy = train_test_split(
                texts, y,
                test_size=settings.train_test_split,
                random_state=settings.random_seed,
                stratify=y,
            )
        else:
            tx, ty = texts, y
            vx, vy = [], np.array([])

        # Fit both vectorizers on training data only.
        self.vectorizer_word.fit(tx)
        self.vectorizer_char.fit(tx)

        X_train = self._vectorize([self.vectorizer_word, self.vectorizer_char], tx)
        self.model.fit(X_train, ty)
        self.classes_ = [c.value for c in EmailClass]

        if not eval_split or len(vy) == 0:
            return None
        X_val = self._vectorize([self.vectorizer_word, self.vectorizer_char], vx)
        preds = self.model.predict(X_val)
        return BaselineMetrics(
            accuracy=accuracy_score(vy, preds),
            precision=precision_score(vy, preds, average="weighted", zero_division=0),
            recall=recall_score(vy, preds, average="weighted", zero_division=0),
            f1=f1_score(vy, preds, average="weighted", zero_division=0),
        )

    def predict(self, texts: Iterable[str]) -> tuple[np.ndarray, np.ndarray]:
        """Return (predicted_indices, probability_matrix)."""
        texts_clean = [clean_text(t) for t in texts]
        X = self._vectorize([self.vectorizer_word, self.vectorizer_char], texts_clean)
        preds = self.model.predict(X)
        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba(X)
        else:
            # CalibratedClassifierCV provides predict_proba; fallback to one-hot.
            one_hot = np.zeros((len(preds), len(self.classes_)))
            one_hot[np.arange(len(preds)), preds] = 1.0
            probs = one_hot
        return preds, probs

    def save(self, path: Path) -> None:
        """Persist the model + vectorizers to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "algorithm": self.algorithm,
                    "vectorizer_word": self.vectorizer_word,
                    "vectorizer_char": self.vectorizer_char,
                    "model": self.model,
                    "classes_": self.classes_,
                },
                f,
            )
        logger.info("Saved baseline model to %s", path)

    @classmethod
    def load(cls, path: Path) -> "BaselineClassifier":
        """Load a persisted model from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        inst = cls(algorithm=data["algorithm"])
        inst.vectorizer_word = data["vectorizer_word"]
        inst.vectorizer_char = data["vectorizer_char"]
        inst.model = data["model"]
        inst.classes_ = data["classes_"]
        return inst