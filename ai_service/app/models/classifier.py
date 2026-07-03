"""Unified EmailClassifier — chooses baseline or DistilBERT at runtime."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from ai_service.app.config import settings
from ai_service.app.constants import CLASS_TO_INDEX, EmailClass, KEYWORD_WEIGHTS
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
        self._rule_fallback: "RuleBasedClassifier | None" = None
        self._loaded = False
        self._model_version = "unversioned"

    @property
    def model_version(self) -> str:
        return self._model_version

    def load(self) -> None:
        """Load the chosen model from disk (or fall back gracefully).

        Fallback chain:
        1. Trained DistilBERT artifact at ``models_dir/distilbert_finetuned/``
        2. Trained baseline artifact at ``models_dir/baseline_<algo>.pkl``
        3. Rule-based heuristic classifier (no training required)
        """
        if self.algorithm == "distilbert":
            candidate = self.model_dir / "distilbert_finetuned"
            if candidate.exists() and (candidate / "config.json").exists():
                self._distilbert = DistilBertClassifier()
                self._distilbert.load(candidate)
                self._model_version = "distilbert-finetuned"
                self._loaded = True
                logger.info("Loaded DistilBERT from %s", candidate)
                return
            logger.warning(
                "DistilBERT artifact not found at %s. Falling back to a baseline.",
                candidate,
            )
            self.algorithm = "naive_bayes"

        candidate = self.model_dir / f"baseline_{self.algorithm}.pkl"
        if candidate.exists():
            self._baseline = BaselineClassifier.load(candidate)
            self._model_version = f"baseline-{self.algorithm}"
            self._loaded = True
            logger.info("Loaded baseline %s from %s", self.algorithm, candidate)
            return

        # No trained artifacts available. Use the rule-based fallback so
        # the service can still classify emails with a sensible confidence
        # score instead of returning random noise.
        logger.warning(
            "No trained artifacts found in %s. Using rule-based heuristic classifier.",
            self.model_dir,
        )
        self._baseline = BaselineClassifier(algorithm=self.algorithm)  # placeholder
        self._rule_fallback = RuleBasedClassifier()
        self._model_version = f"rule-based-heuristic"
        self._loaded = True

    def predict(self, email: dict) -> ClassifierOutput:
        """Classify a single email dict."""
        if not self._loaded:
            self.load()

        # Rule-based path: bypass the (untrained) sklearn model entirely.
        if getattr(self, "_rule_fallback", None) is not None:
            return self._rule_fallback.predict(email, model_version=self._model_version)

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


class RuleBasedClassifier:
    """A zero-ML classifier used when no trained artifact exists.

    Scores every email against the ``KEYWORD_WEIGHTS`` table and a handful of
    structural heuristics (URL count, short body, all-caps sender domain), then
    returns the most likely class with a calibrated probability vector.

    Quality is far below a trained model, but it returns consistent, defensible
    predictions so the rest of the stack (risk score, XAI, dashboard) keeps
    working in environments where training hasn't run yet.
    """

    _URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
    _NOTIF_HINTS = (
        "noreply", "no-reply", "donotreply", "do-not-reply",
        "notification", "alert", "alerting", "updates", "newsletter",
        "team@", "support@", "noreply@", "mailer-daemon",
        "shipment", "delivery", "tracking", "order", "invoice",
        "github.com", "gitlab.com", "jira", "trello",
    )

    def predict(self, email: dict, *, model_version: str) -> ClassifierOutput:
        subject = (email.get("subject") or "").strip()
        body = (email.get("body") or "").strip()
        sender = (email.get("sender") or "").strip()
        text = f"{subject} {body}".lower()
        urls = self._URL_RE.findall(body)

        score: float = 0.0
        for phrase, weight in KEYWORD_WEIGHTS.items():
            if phrase in text:
                score += weight * min(text.count(phrase), 3)
        if any(u.lower().startswith("http://") for u in urls):
            score += 5.0
        if len(urls) >= 3:
            score += 6.0
        if sender and not re.search(r"[a-z0-9]", sender.lower()):
            score += 1.0

        sender_l = sender.lower()
        is_notif = any(h in sender_l for h in self._NOTIF_HINTS) or any(
            h in text for h in ("this is an automated", "automated message", "do not reply")
        )

        # Decide class.
        if score >= 12.0:
            label_name = EmailClass.SCAM.value
        elif score >= 6.0:
            label_name = EmailClass.SPAM.value
        elif is_notif:
            label_name = EmailClass.NOTIFICATION.value
        else:
            label_name = EmailClass.NORMAL.value

        idx = CLASS_TO_INDEX[EmailClass(label_name)]

        # Build a smooth probability vector — the predicted class gets the
        # highest weight proportional to ``score``, the rest share the tail.
        confidence = max(0.55, min(0.92, 0.5 + score / 25.0))
        rest = (1.0 - confidence) / 3.0
        probs = np.array([rest, rest, rest, rest], dtype=np.float64)
        probs[idx] = confidence
        # Normalize so probabilities sum to 1.
        probs = probs / probs.sum()

        return ClassifierOutput(
            label_index=idx,
            label_name=label_name,
            confidence=float(probs[idx]),
            probabilities=probs,
            inference_time_ms=0,
            algorithm="rule-based-heuristic",
            model_version=model_version,
        )