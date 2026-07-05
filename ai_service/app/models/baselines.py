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
from sklearn.linear_model import LogisticRegression
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

    def __init__(self, algorithm: str = "naive_bayes", class_weight: str | None = "balanced"):
        if algorithm not in {"naive_bayes", "svm", "random_forest", "logistic_regression"}:
            raise ValueError(f"Unknown baseline algorithm: {algorithm}")
        self.algorithm = algorithm
        self.class_weight = class_weight
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
        self.model = self._build_model(algorithm, class_weight=class_weight)
        self.classes_: list[str] = []

    @staticmethod
    def _build_model(algorithm: str, class_weight: str | None = "balanced"):
        if algorithm == "naive_bayes":
            # Naive Bayes doesn't natively support class_weight on
            # MultinomialNB. We re-weight the training samples upstream
            # instead (handled in `fit`).
            return MultinomialNB(alpha=0.1)
        if algorithm == "svm":
            # CalibratedClassifierCV doesn't forward class_weight to its
            # base estimator; we rely on sample_weight computed from
            # class frequencies in `fit`.
            return CalibratedClassifierCV(LinearSVC(C=1.0), cv=3)
        if algorithm == "logistic_regression":
            # LR natively supports class_weight — best baseline for
            # accurate probabilities and balanced decisions.
            return LogisticRegression(
                max_iter=2000,
                C=1.0,
                class_weight=class_weight or "balanced",
                solver="lbfgs",
                random_state=settings.random_seed,
                n_jobs=-1,
            )
        return RandomForestClassifier(
            n_estimators=200,
            n_jobs=-1,
            random_state=settings.random_seed,
            class_weight=class_weight or "balanced_subsample",
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

        # Compute sample_weight from class frequencies to compensate for
        # the heavily unbalanced dataset (normal is ~75% of merged corpus).
        # sklearn's `class_weight="balanced"` works natively for RandomForest
        # but is silently ignored by MultinomialNB and CalibratedClassifierCV,
        # so we replicate the balancing via sample_weight instead.
        sw = None
        try:
            from sklearn.utils.class_weight import compute_sample_weight
            sw = compute_sample_weight(
                class_weight=self.class_weight or "balanced", y=ty,
            )
        except Exception:
            sw = None
        try:
            if sw is not None:
                self.model.fit(X_train, ty, sample_weight=sw)
            else:
                self.model.fit(X_train, ty)
        except TypeError:
            # Older scikit-learn signatures don't accept sample_weight here.
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
                    "class_weight": self.class_weight,
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
        inst = cls(
            algorithm=data["algorithm"],
            class_weight=data.get("class_weight", "balanced"),
        )
        inst.vectorizer_word = data["vectorizer_word"]
        inst.vectorizer_char = data["vectorizer_char"]
        inst.model = data["model"]
        inst.classes_ = data["classes_"]
        return inst