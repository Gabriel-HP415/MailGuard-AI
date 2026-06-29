"""Application-wide constants and enumerations."""

from enum import Enum


class EmailClass(str, Enum):
    """The 4 classes of email classification."""

    NORMAL = "normal"
    NOTIFICATION = "notification"
    SPAM = "spam"
    SCAM = "scam"

    @property
    def index(self) -> int:
        return _CLASS_TO_INDEX[self]


class ThreatLevel(str, Enum):
    """Risk-based threat level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UserRole(str, Enum):
    """User authorization role."""

    USER = "user"
    ADMIN = "admin"


class ModelAlgorithm(str, Enum):
    """Supported ML algorithms."""

    NAIVE_BAYES = "naive_bayes"
    SVM = "svm"
    RANDOM_FOREST = "random_forest"
    DISTILBERT = "distilbert"


# Numeric label mapping used during training.
_CLASS_TO_INDEX = {
    EmailClass.NORMAL: 0,
    EmailClass.NOTIFICATION: 1,
    EmailClass.SPAM: 2,
    EmailClass.SCAM: 3,
}

INDEX_TO_CLASS = {idx: cls.value for cls, idx in _CLASS_TO_INDEX.items()}


def class_from_index(idx: int) -> EmailClass:
    """Map numeric label back to EmailClass."""
    return EmailClass(INDEX_TO_CLASS.get(idx, EmailClass.NORMAL.value))


# Risk score thresholds (0–100).
RISK_THRESHOLDS = {
    ThreatLevel.LOW: (0, 25),
    ThreatLevel.MEDIUM: (26, 50),
    ThreatLevel.HIGH: (51, 75),
    ThreatLevel.CRITICAL: (76, 100),
}


def threat_from_score(score: float) -> ThreatLevel:
    """Convert a 0-100 risk score to a ThreatLevel."""
    for level, (low, high) in RISK_THRESHOLDS.items():
        if low <= score <= high:
            return level
    return ThreatLevel.LOW