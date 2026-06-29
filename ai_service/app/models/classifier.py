"""Unified EmailClassifier — chooses baseline or DistilBERT at runtime."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from ai_service.app.config import settings
from ai_service.app.constants import CLASS_TO_INDEX, EmailClass
from ai_service.app.models.distilbert_classifier import DistilBertClassifier
from ai_service.app.models.baselines import BaselineClassifier
from ai_service.app.preprocessing.text_cleaner import normalize_email

logger = logging.getLogger(__name__)


@dataclass
class ClassifierOutput:
    """Output of the unified EmailClassifier."""

    label_index: int
    label_name: str
    confidence: float
    probabilities: np.ndarray
    inference_time_ms: int
    algorithm: str
    model_version: str


class EmailClassifier:
    """A high-level classifier that abstracts baseline vs DistilBERT."""

    def __init__(self, algorithm: str = "auto", model_dir: Path | None = None):
        self.algorithm = algorithm if algorithm != "auto" else settings.baseline_model
        self.model_dir = model_dir or settings.models_dir
        self._distilbert: DistilBertClassifier | None = None
        self._baseline: BaselineClassifier | None = None
        self._loaded = False
        self._model_version = "unversioned"

    @property
    def model_version(self) -> str:
        return self._model_version

    def load(self) -> None:
        """Load the chosen model from disk (or fall back to a baseline)."""
        if self.algorithm == "distilbert":
            candidate = self.model_dir / "distilbert_finetuned"
            if not candidate.exists():
                logger.warning(
                    "DistilBERT artifact not found at %s. Falling back to a baseline.",
                    candidate,
                )
                self.algorithm = "naive_bayes"
            else:
                self._distilbert = DistilBertClassifier()
                self._distilbert.load(candidate)
                self._model_version = "distilbert-finetuned"
                self._loaded = True
                return

        # Baseline branch.
        candidate = self.model_dir / f"baseline_{self.algorithm}.pkl"
        if candidate.exists():
            self._baseline = BaselineClassifier.load(candidate)
            self._model_version = f"baseline-{self.algorithm}"
            self._loaded = True
        else:
            # Last resort: build a fresh, untrained baseline (zero useful predictions).
            logger.warning(
                "No baseline artifact at %s. Creating an untrained %s classifier.",
                candidate, self.algorithm,
            )
            self._baseline = BaselineClassifier(algorithm=self.algorithm)
            self._model_version = f"baseline-{self.algorithm}-untrained"
            self._loaded = True

    def predict(self, email: dict) -> ClassifierOutput:
        """Classify a single email dict."""
        if not self._loaded:
            self.load()
        if self._distilbert is not None:
            out = self._distilbert.predict(email)
            return ClassifierOutput(
                label_index=out.label_index,
                label_name=out.label_name,
                confidence=out.confidence,
                probabilities=out.probabilities,
                inference_time_ms=out.inference_time_ms,
                algorithm="distilbert",
                model_version=self._model_version,
            )
        text = normalize_email(
            subject=email.get("subject"),
            body=email.get("body"),
            sender=email.get("sender"),
        )
        idx, probs = self._baseline.predict([text])
        return ClassifierOutput(
            label_index=int(idx[0]),
            label_name=class_from_index(int(idx[0])).value,
            confidence=float(np.max(probs[0])),
            probabilities=probs[0],
            inference_time_ms=0,
            algorithm=self.algorithm,
            model_version=self._model_version,
        )

    def predict_batch(self, emails: list[dict]) -> list[ClassifierOutput]:
        return [self.predict(e) for e in emails]


def class_from_index(idx: int) -> EmailClass:
    for cls, i in CLASS_TO_INDEX.items():
        if i == idx:
            return cls
    return EmailClass.NORMAL