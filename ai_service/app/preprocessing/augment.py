"""Data augmentation for imbalanced training data.

Goal: enlarge minority classes (typically `scam` and `spam`) by generating
paraphrased variants of existing samples. We use lightweight, dependency-free
techniques so this works without GPU or external services:

1. **Synonym replacement** — swap a small set of known phishing/spam keywords
   with close alternates (e.g. "verify" -> "confirm", "click here" -> "tap").
2. **Sentence shuffling** — reorder clauses for messages with multiple
   sentences.
3. **HTML noise injection** — add invisible characters (NBSPs, zero-width
   spaces) to mimic adversarial obfuscation.
4. **Whitespace obfuscation** — duplicate random characters in URLs to
   approximate lookalike domains.

For higher-quality paraphrases, you can swap in a back-translation helper
behind the ``--use-back-translation`` flag, which requires
``transformers`` + a translation model.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence


# ============================================================
# Augmentation primitives
# ============================================================

# Built-in synonym map. Keys are matched case-insensitively on whole words.
DEFAULT_SYNONYMS: dict[str, list[str]] = {
    "verify": ["confirm", "validate", "authenticate", "check"],
    "confirm": ["verify", "validate", "re-check"],
    "click": ["tap", "press", "hit", "select"],
    "here": ["below", "this link", "right here"],
    "account": ["profile", "membership", "user profile"],
    "password": ["passcode", "login credentials", "access code"],
    "urgent": ["immediate", "critical", "time-sensitive", "pressing"],
    "immediately": ["right now", "as soon as possible", "at once"],
    "winner": ["lucky recipient", "selected candidate", "chosen user"],
    "prize": ["reward", "gift", "bonus"],
    "free": ["complimentary", "no-cost", "bonus"],
    "limited": ["exclusive", "restricted", "short"],
    "offer": ["deal", "promotion", "opportunity"],
    "security": ["protection", "safety", "verification"],
    "update": ["refresh", "renew", "patch"],
    "suspended": ["locked", "disabled", "frozen"],
    "expire": ["end", "run out", "lapse"],
    "login": ["sign in", "log on", "authenticate"],
    "important": ["critical", "essential", "vital"],
    "congratulations": ["well done", "congrats", "kudos"],
}


_NBSP = "\u00a0"
_ZWSP = "\u200b"
_INVISIBLES = [_NBSP, _ZWSP, "\u200c"]


def _word_swap(text: str, swap_prob: float, rng: random.Random) -> str:
    """Replace words found in DEFAULT_SYNONYMS with a random synonym."""
    out_words: list[str] = []
    for word in text.split():
        # Preserve trailing punctuation
        m = re.match(r"^(\W*)([\w'-]+)(\W*)$", word)
        if not m:
            out_words.append(word)
            continue
        prefix, core, suffix = m.groups()
        key = core.lower().strip("'\"")
        if key in DEFAULT_SYNONYMS and rng.random() < swap_prob:
            replacement = rng.choice(DEFAULT_SYNONYMS[key])
            # Preserve capitalization of the first letter
            if core[0].isupper():
                replacement = replacement.capitalize()
            out_words.append(f"{prefix}{replacement}{suffix}")
        else:
            out_words.append(word)
    return " ".join(out_words)


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _sentence_shuffle(text: str, rng: random.Random) -> str:
    """Randomly swap adjacent sentences 50% of the time."""
    sentences = _SENTENCE_RE.split(text.strip())
    if len(sentences) < 2:
        return text
    # Pairwise shuffle, easy to keep coherent
    for i in range(0, len(sentences) - 1, 2):
        if rng.random() < 0.4:
            sentences[i], sentences[i + 1] = sentences[i + 1], sentences[i]
    return " ".join(sentences)


_URL_RE = re.compile(r"https?://[^\s<>\"']+")


def _obfuscate_urls(text: str, rng: random.Random, prob: float = 0.3) -> str:
    """Inject zero-width / non-breaking spaces into URLs (looks like phishing)."""
    def _noise(match: re.Match) -> str:
        if rng.random() > prob:
            return match.group(0)
        url = match.group(0)
        if len(url) < 12:
            return url
        i = rng.randrange(6, len(url) - 2)
        return url[:i] + rng.choice(_INVISIBLES) + url[i:]

    return _URL_RE.sub(_noise, text)


def _invisible_chars(text: str, rng: random.Random, density: float = 0.02) -> str:
    """Inject rare invisible characters between words for adversarial noise."""
    out: list[str] = []
    for ch in text:
        out.append(ch)
        if ch == " " and rng.random() < density:
            out.append(rng.choice(_INVISIBLES))
    return "".join(out)


# ============================================================
# Public API
# ============================================================


@dataclass
class AugmentedSample:
    text: str
    subject: str
    strategy: str


def augment_text(
    text: str,
    *,
    strategies: Sequence[str] = ("synonym", "shuffle", "url_noise"),
    swap_prob: float = 0.18,
    rng: random.Random | None = None,
) -> list[str]:
    """Return N augmented variants of ``text`` (one per strategy)."""
    rng = rng or random.Random()
    out: list[str] = []
    if "synonym" in strategies:
        out.append(_word_swap(text, swap_prob, rng))
    if "shuffle" in strategies:
        out.append(_sentence_shuffle(text, rng))
    if "url_noise" in strategies:
        out.append(_obfuscate_urls(text, rng))
    if "invisible" in strategies:
        out.append(_invisible_chars(text, rng))
    return out


def augment_dataset(
    samples: Iterable[tuple[str, str, str]],
    *,
    target_classes: Sequence[str] = ("scam", "spam"),
    multiplier: int = 2,
    seed: int = 42,
) -> List[tuple[str, str, str]]:
    """Augment only the target minority classes.

    ``samples`` is an iterable of ``(label, subject, body)`` tuples.
    Returns the original samples plus augmented copies for each row whose
    label is in ``target_classes`` (each original spawns ``multiplier``
    new rows).
    """
    rng = random.Random(seed)
    out: list[tuple[str, str, str]] = []
    for label, subject, body in samples:
        out.append((label, subject, body))
        if label not in target_classes:
            continue
        for _ in range(multiplier):
            variants = augment_text(body, rng=rng)
            for v in variants:
                out.append((label, subject, v))
    return out


def class_distribution(samples: Iterable[tuple[str, str, str]]) -> dict[str, int]:
    """Return counts of each label in ``samples`` (for sanity-checking)."""
    counts: dict[str, int] = {}
    for label, _, _ in samples:
        counts[label] = counts.get(label, 0) + 1
    return counts