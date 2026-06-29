"""Models package — baselines, DistilBERT classifier, ensemble, registry."""

from ai_service.app.models.baselines import BaselineClassifier, BaselineMetrics
from ai_service.app.models.classifier import EmailClassifier
from ai_service.app.models.registry import ModelRegistry

__all__ = [
    "BaselineClassifier",
    "BaselineMetrics",
    "EmailClassifier",
    "ModelRegistry",
]