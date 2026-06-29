"""Constants used by the AI Service."""

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


CLASS_TO_INDEX = {
    EmailClass.NORMAL: 0,
    EmailClass.NOTIFICATION: 1,
    EmailClass.SPAM: 2,
    EmailClass.SCAM: 3,
}

INDEX_TO_CLASS = {idx: cls.value for cls, idx in CLASS_TO_INDEX.items()}


def class_from_index(idx: int) -> EmailClass:
    return EmailClass(INDEX_TO_CLASS.get(idx, EmailClass.NORMAL.value))


# Suspicious TLDs commonly used in phishing/scam.
SUSPICIOUS_TLDS = {
    ".zip", ".mov", ".xyz", ".top", ".click", ".country", ".kim",
    ".work", ".gq", ".tk", ".ml", ".cf", ".ga", ".pw",
}

# Phishing / scam keyword weights.
KEYWORD_WEIGHTS: dict[str, float] = {
    # Account & security
    "verify your account": 3.0,
    "verify account": 2.5,
    "suspend": 2.0,
    "locked": 2.0,
    "unlock": 2.0,
    "confirm your identity": 2.5,
    "update your password": 2.5,
    "security alert": 1.5,
    "unusual activity": 1.5,
    # Money / urgency
    "urgent": 1.5,
    "immediately": 1.5,
    "act now": 2.0,
    "limited time": 1.0,
    "winner": 1.5,
    "congratulations": 1.0,
    "you have been selected": 2.0,
    "claim your prize": 2.0,
    "free": 1.0,
    "100% free": 2.0,
    "click here": 1.5,
    "click below": 1.0,
    # Money transfer
    "wire transfer": 2.0,
    "gift card": 2.5,
    "bitcoin": 2.0,
    "cryptocurrency": 1.5,
    "bank account": 1.5,
    "tax refund": 2.0,
    "inheritance": 2.0,
    "million dollars": 2.5,
    # Generic spam
    "viagra": 3.0,
    "cialis": 3.0,
    "lose weight": 2.0,
    "make money": 1.5,
    "work from home": 1.0,
    # Threats
    "legal action": 1.5,
    "lawsuit": 1.5,
    "police": 1.0,
    "arrest warrant": 2.5,
}

# URL-shortener / known-bad patterns used for risk scoring.
URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
    "buff.ly", "adf.ly", "rebrand.ly", "cutt.ly", "shorturl.at",
}

# Common legitimate email providers (used as weak signal).
KNOWN_PROVIDERS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
    "yahoo.com", "icloud.com", "protonmail.com", "proton.me",
}