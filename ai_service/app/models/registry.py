"""Model registry — manages the currently active model version in memory."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from ai_service.app.config import settings
from ai_service.app.models.classifier import EmailClassifier

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Thread-safe singleton holding the active EmailClassifier."""

    _instance: "ModelRegistry | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "ModelRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._classifier = None
                    cls._instance._initialised = False
        return cls._instance

    def get_classifier(self) -> EmailClassifier:
        if not self._initialised or self._classifier is None:
            with self._lock:
                if not self._initialised or self._classifier is None:
                    self._classifier = EmailClassifier(
                        algorithm=settings.baseline_model,
                        model_dir=settings.models_dir,
                    )
                    try:
                        self._classifier.load()
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Failed to load AI model: %s", exc)
                    self._initialised = True
        return self._classifier

    def reload(self, algorithm: str | None = None) -> EmailClassifier:
        """Force a reload of the underlying model."""
        with self._lock:
            algo = algorithm or settings.baseline_model
            self._classifier = EmailClassifier(algorithm=algo, model_dir=settings.models_dir)
            self._classifier.load()
            self._initialised = True
            return self._classifier


registry = ModelRegistry()