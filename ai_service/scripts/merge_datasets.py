"""Merge multiple public datasets into a unified 4-class CSV.

This module pulls three well-known corpora that match the three Kaggle
notebooks the project started from:

1. **Enron emails** (parse-and-process-enron-emails-dataset)
   - Source 1: `corbt/enron-emails` on Hugging Face — 500K raw email
     messages from the Enron corpus, all treated as `normal` (ham).
   - Source 2: `bvk/ENRON-spam` on Hugging Face — the Metsis et al. 2006
     Enron subset (33,716 messages) with explicit spam/ham labels; we keep
     the spam rows to enrich the `spam` class.
   - The first source ships as a ZIP of CSV parts; the second is a single
     CSV. Both are streamed to keep memory low.

2. **Phishing email detection** (phishing-email-detection-using-deep-learning)
   - Source: `zefang-liu/phishing-email-dataset` on Hugging Face — a copy
     of the Kaggle "Phishing_Email.csv" (18,650 rows) with columns
     `subject`, `body`, `label` ∈ {Safe Email, Phishing Email}.
   - Mapping: Phishing Email → `scam`, Safe Email → `normal`.

3. **SMS / Spam email classifier** (spam-email-classifier)
   - Source: the SMS Spam Collection mirrored on GitHub
     (`codebasics/py/ML/14_naive_bayes/spam.csv`) — 5,572 messages with
     `Category` ∈ {ham, spam} and `Message` text.
   - Per project decision, all SMS rows are mapped to `notification` since
     SMS-style messages are short transactional / promotional notifications
     rather than full emails.

4. **Synthetic normal / notification** — added to round out the classes
   when one of the public downloads fails (e.g. offline). Provides
   additional examples for classes that are scarce in the public data.

Output: ``datasets/merged_dataset.csv`` with columns
``label, subject, body, source``.

The merge is idempotent and resilient: any single source that fails to
download is logged and skipped, the rest of the merge still completes.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import urllib.request
import zipfile
from dataclasses import dataclass
from email.utils import parseaddr
from pathlib import Path
from typing import Callable, Iterable, Iterator

from ai_service.app.config import settings

# Some public CSVs (phishing_email.csv, Enron_Txt_fn.csv) contain individual
# fields well over Python's default csv field limit (131 KB). Raise the limit
# before any csv.reader / DictReader is used so the parsers don't truncate.
csv.field_size_limit(100 * 1024 * 1024)

logger = logging.getLogger(__name__)


# ============================================================
# Dataset source URLs (no auth required)
# ============================================================

# 1a. Enron — `corbt/enron-emails` (raw email corpus, treated as normal).
# The dataset was republished as 3 parquet shards under `data/`. Each shard
# is ~165 MB; we download just the first one to keep the merge fast and the
# raw archive small.
ENRON_HF_BASE = (
    "https://huggingface.co/datasets/corbt/enron-emails/resolve/main/"
)
ENRON_HF_FILES = (
    "data/train-00000-of-00003.parquet",
)

# 1b. Enron — `bvk/ENRON-spam` (Metsis subset, labelled spam/ham). The
# actual file in the dataset is `Enron_Txt_fn.csv`; the older URL
# (ENRON_spam.csv) 404s on the current HF revision.
ENRON_SPAM_HF_URL = (
    "https://huggingface.co/datasets/bvk/ENRON-spam/resolve/main/Enron_Txt_fn.csv"
)

# 2. Phishing email detection — `zefang-liu/phishing-email-dataset`
PHISHING_HF_URL = (
    "https://huggingface.co/datasets/zefang-liu/phishing-email-dataset/"
    "resolve/main/Phishing_Email.csv"
)

# 3. SMS Spam Collection (mirrored in the codebasics py repo)
SMS_SPAM_GITHUB_URL = (
    "https://raw.githubusercontent.com/codebasics/py/master/ML/14_naive_bayes/spam.csv"
)

# Fallback mirrors (used if the primary URL fails)
SMS_SPAM_FALLBACK_URLS = (
    "https://raw.githubusercontent.com/mohitgupta-1O1/"
    "Kaggle-SMS-Spam-Collection-Dataset-/master/spam.csv",
)


# ============================================================
# Helpers
# ============================================================


@dataclass
class Sample:
    """A unified email sample."""

    label: str  # normal | notification | spam | scam
    subject: str
    body: str
    source: str


def _download(url: str, dest: Path, *, force: bool = False) -> Path:
    """Download a file to ``dest`` (skip if already present unless ``force``)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force and dest.stat().st_size > 0:
        return dest
    logger.info("Downloading %s -> %s", url, dest)
    req = urllib.request.Request(
        url, headers={"User-Agent": "MailGuard-AI/1.0 (+https://mailguard.ai)"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    dest.write_bytes(data)
    return dest


def _try_download(urls: Iterable[str], dest: Path) -> Path | None:
    """Try each URL in order; return the first that succeeds."""
    last_exc: Exception | None = None
    for url in urls:
        try:
            return _download(url, dest)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("Download failed (%s): %s", url, exc)
    if last_exc:
        logger.error("All mirrors failed for %s: %s", dest.name, last_exc)
    return None


def _stream_csv_lines(
    fp: Path,
    chunk_size: int = 1024 * 1024,
) -> Iterator[str]:
    """Yield decoded text lines from a CSV file in chunks (low memory)."""
    with open(fp, "rb") as f:
        buf = ""
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                if buf:
                    yield buf
                break
            buf += chunk.decode("utf-8", errors="ignore")
            while "\n" in buf:
                line, _, buf = buf.partition("\n")
                yield line


# ============================================================
# 1a. Enron raw emails (corbt/enron-emails) — all normal
# ============================================================

_ENRON_HEADER_RE = re.compile(r"^([A-Za-z\-]+):\s*(.*)$")
_ENRON_FROM_RE = re.compile(r"^From:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_ENRON_SUBJECT_RE = re.compile(r"^Subject:\s*(.*)$", re.IGNORECASE | re.MULTILINE)


def _parse_enron_message(raw: str) -> tuple[str, str]:
    """Return (subject, body) from a raw RFC-822 email string.

    Enron rows are formatted as:
        Message-ID: ...
        Date: ...
        From: ...
        To: ...
        Subject: ...
        ...
        (blank line)
        <body>
    """
    # Split headers from body on the first blank line
    parts = raw.split("\n\n", 1)
    header_block = parts[0]
    body = parts[1].strip() if len(parts) > 1 else ""

    m = _ENRON_SUBJECT_RE.search(header_block)
    subject = m.group(1).strip() if m else ""

    if not body:
        # Some rows have no body at all — treat the entire message as body
        body = raw.strip()
    return subject, body[:8000]


def _iter_enron_normal(max_samples: int | None = None) -> Iterable[Sample]:
    """Yield ``normal`` samples from the Enron parquet shards.

    The corbt/enron-emails dataset is published as Parquet since 2024 — the
    legacy `emails.csv.zip` URL 404s. Each row has columns ``message``
    (raw RFC-822 email text), ``subject`` (parsed subject, may be empty),
    and ``file`` (path on disk in the original Enron release).
    """
    import pandas as pd  # lazy import — pandas is only needed here

    raw_dir = settings.datasets_dir / "raw"
    parquet_url = ENRON_HF_BASE + ENRON_HF_FILES[0]
    parquet_path = _try_download(
        [parquet_url],
        raw_dir / "enron_train_00000.parquet",
    )
    if parquet_path is None:
        return

    logger.info("Reading Enron parquet: %s", parquet_path)
    df = pd.read_parquet(parquet_path)
    # The shard ships with at least `message` and `subject`; use whichever
    # non-empty column carries the body.
    msg_col = next(
        (c for c in ("message", "text", "body") if c in df.columns), None,
    )
    subj_col = next(
        (c for c in ("subject", "Subject") if c in df.columns), None,
    )
    if msg_col is None:
        logger.error("Enron parquet missing message column: %s", df.columns.tolist())
        return

    count = 0
    for _, row in df.iterrows():
        raw = row.get(msg_col) if hasattr(row, "get") else row[msg_col]
        if not raw or "From:" not in str(raw):
            continue
        subject, body = _parse_enron_message(str(raw))
        if not body:
            continue
        # Subject is also stored as a parquet column for many rows; use it
        # when the header parsing didn't produce one.
        if not subject and subj_col:
            candidate = row.get(subj_col) if hasattr(row, "get") else row[subj_col]
            if candidate and isinstance(candidate, str) and candidate.strip():
                subject = candidate.strip()
        yield Sample(
            label="normal",
            subject=subject[:500],
            body=body,
            source="enron_corbt",
        )
        count += 1
        if max_samples and count >= max_samples:
            break
    logger.info("Enron (corbt parquet): %d normal samples", count)


# ============================================================
# 1b. Enron-spam (bvk/ENRON-spam) — labelled spam
# ============================================================

def _iter_enron_spam(max_samples: int | None = None) -> Iterable[Sample]:
    """Yield ``spam``/``normal`` samples from the Metsis Enron spam subset.

    The bvk/ENRON-spam CSV uses columns ``label,email,filename``:
      - ``label`` is ``0`` (ham) or ``1`` (spam)
      - ``email`` is a single quoted blob like ``['Subject: foo\\nbody']``
        where the body is a Python repr string (escaped ``\\n``, ``\\r``,
        ``\\\\``, ``\\xNN`` etc.)

    The file is malformed in many places (unbalanced quotes, mixed
    separators inside URLs), so we use ``python`` csv engine with
    ``on_bad_lines='skip'`` (rather than raising mid-parse).
    """
    raw_dir = settings.datasets_dir / "raw"
    csv_path = _try_download(
        [ENRON_SPAM_HF_URL],
        raw_dir / "enron_spam.csv",
    )
    if csv_path is None:
        return

    decoded_cache: dict[int, str] = {}
    raw_bytes = csv_path.read_bytes()
    # Coarse fix-up: line endings + stray quotes that csv.reader trips on.
    text = raw_bytes.decode("utf-8", errors="ignore")

    count = 0
    for line_idx, line in enumerate(text.splitlines()):
        if line_idx == 0:
            # Skip header — we know the format: label,email,filename
            continue
        line = line.strip()
        if not line:
            continue
        if not (line.startswith("0,") or line.startswith("1,")):
            continue
        # Parse: first char = label, last comma-separated token = filename,
        # middle is a quoted email blob wrapped by '"[''...'']"'.
        first_comma = line.find(",")
        if first_comma < 0:
            continue
        label_raw = line[:first_comma].strip()
        # The filename is after the LAST comma. Everything in between
        # belongs to the email column. Inside that we expect `'[... ... ]'`
        # as a quoted JSON-ish Python list literal.
        last_comma = line.rfind(",")
        if last_comma <= first_comma:
            continue
        content_raw = line[first_comma + 1: last_comma].strip()
        # Strip surrounding quotes (single or double) that wrap the literal.
        if (content_raw.startswith("'") and content_raw.endswith("'")) or (
            content_raw.startswith('"') and content_raw.endswith('"')
        ):
            content_raw = content_raw[1:-1]
        # The body is inside `'[ ... ]'`. Sometimes the outer wrapper is
        # double quotes around single-quoted Python list. Unwrap both.
        if content_raw.startswith("'[") and content_raw.endswith("]'"):
            content_raw = content_raw[2:-2]
        elif content_raw.startswith('"[') and content_raw.endswith(']"'):
            content_raw = content_raw[2:-2]
        elif content_raw.startswith("[") and content_raw.endswith("]"):
            content_raw = content_raw[1:-1]
        try:
            content = content_raw.encode("utf-8").decode(
                "unicode_escape", errors="ignore",
            )
        except Exception:
            content = content_raw
        if not content.strip():
            continue
        # Extract subject
        subject = ""
        m = re.search(r"Subject:\s*([^\n\\]+)", content, re.IGNORECASE)
        if m:
            subject = m.group(1).strip()
        body = content
        if subject:
            # Strip the Subject: line from the body so the model sees the
            # body alone, not duplicated content.
            body = re.sub(r"^Subject:.*?\n", "", body, count=1, flags=re.IGNORECASE)

        label_norm = label_raw.lower()
        target_label = None
        if label_norm in {"1", "spam", "phishing", "scam"}:
            target_label = "spam"
        elif label_norm in {"0", "ham", "safe email", "normal", "legit"}:
            target_label = "normal"
        if target_label is None:
            continue
        yield Sample(
            label=target_label,
            subject=subject[:500],
            body=body[:8000],
            source="enron_spam_bvk",
        )
        count += 1
        if max_samples and count >= max_samples:
            break
    logger.info("Enron-spam (bvk txt): %d samples", count)


# ============================================================
# 2. Phishing email detection — safe vs phishing
# ============================================================

def _iter_phishing(max_samples: int | None = None) -> Iterable[Sample]:
    """Yield ``scam`` / ``normal`` samples from Phishing_Email.csv.

    The published CSV format is ``Unnamed: 0, "Email Text", "Email Type"``
    where ``Email Type`` is ``"Safe Email"`` or ``"Phishing Email"``.
    Many rows contain unescaped commas inside the body and exceed the
    default field size limit; we use the python csv engine with the
    raised limit set at module top.
    """
    raw_dir = settings.datasets_dir / "raw"
    csv_path = _try_download([PHISHING_HF_URL], raw_dir / "phishing_email.csv")
    if csv_path is None:
        return

    # Two passes: first find the column indices by sniffing the header,
    # then stream rows using fixed column positions so we never depend on
    # csv writing to put the label where we expect.
    header: list[str] = []
    with open(csv_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        header = [h.strip().lower() for h in next(csv.reader(f))]
        text_idx = 0
        label_idx = len(header) - 1
        for i, h in enumerate(header):
            if "text" in h or "email" in h:
                text_idx = i
                break
        for i, h in enumerate(header):
            if "type" in h or "label" in h or "class" in h:
                label_idx = i
                break

    count = 0
    with open(csv_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if not row:
                continue
            label = (row[label_idx] if label_idx < len(row) else "").strip().lower()
            text = (row[text_idx] if text_idx < len(row) else "").strip()
            if not text or text.lower() == "empty":
                continue
            if "phishing" in label:
                target = "scam"
            elif "safe" in label or "ham" in label or "legitimate" in label:
                target = "normal"
            else:
                continue
            yield Sample(
                label=target,
                subject="",
                body=text[:8000],
                source="phishing_kaggle",
            )
            count += 1
            if max_samples and count >= max_samples:
                break
    logger.info("Phishing: %d samples (mapped to scam/normal)", count)


# ============================================================
# 3. SMS Spam Collection — all treated as notification
# ============================================================

def _iter_sms(max_samples: int | None = None) -> Iterable[Sample]:
    """Yield ``notification`` samples from spam.csv (Category, Message)."""
    raw_dir = settings.datasets_dir / "raw"
    csv_path = _try_download(
        [SMS_SPAM_GITHUB_URL, *SMS_SPAM_FALLBACK_URLS],
        raw_dir / "sms_spam.csv",
    )
    if csv_path is None:
        return

    count = 0
    with open(csv_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return
        for row in reader:
            if len(row) < 2:
                continue
            category = (row[0] or "").strip().lower()
            message = (row[1] or "").strip()
            if not message:
                continue
            # Per project decision: ALL SMS rows are mapped to notification
            yield Sample(
                label="notification",
                subject=f"[SMS-{category}]",  # keep the original category as a hint
                body=message[:1000],
                source="sms_spam_collection",
            )
            count += 1
            if max_samples and count >= max_samples:
                break
    logger.info("SMS spam (as notification): %d samples", count)


# ============================================================
# 4. Synthetic fallbacks
# ============================================================

_SYNTH_NOTIF_TEMPLATES = [
    ("Your order #12345 has shipped", "Hi {name}, your order has shipped and is on its way. Track it here: https://example.com/track/{id}"),
    ("New login from Chrome on Windows", "We detected a new login to your account from Chrome on Windows. If this was you, no action is needed."),
    ("Your monthly statement is ready", "Your statement for the month is now available in your account dashboard."),
    ("Meeting reminder: Weekly Sync", "This is a reminder that your weekly sync starts in 15 minutes."),
    ("Password changed successfully", "Your password was recently changed. If you did not do this, contact support."),
    ("Package delivered", "Your package was delivered to your front door at 2:35 PM."),
    ("Calendar invite: Design review", "You have been invited to Design review on Friday at 3pm."),
    ("Two-factor code: 382915", "Use code 382915 to finish signing in. The code expires in 10 minutes."),
    ("Your subscription renewed", "Your annual subscription was renewed successfully. The next charge is on the same date next year."),
    ("Flight check-in open", "Check-in for flight AB1234 is now open. Please confirm your seat before departure."),
]


_SYNTH_NORMAL_TEMPLATES = [
    ("Lunch on Friday?", "Hey, are we still on for lunch on Friday? Let me know what time works."),
    ("Re: Project update", "Hi team, attaching the latest project update. Let me know if you have questions."),
    ("Quarterly report draft", "Please find the quarterly report draft attached. Feedback is welcome by EOD."),
    ("Vacation photos", "I uploaded the photos from the trip. Let me know if you want me to share a folder."),
    ("Quick question", "Do you have a minute to chat about the deployment? I have a few questions."),
    ("Family weekend", "We're thinking of coming to visit next weekend. Would you be around?"),
]


def _iter_synthetic_normal(n: int = 500) -> Iterable[Sample]:
    for i in range(n):
        subj, body = _SYNTH_NORMAL_TEMPLATES[i % len(_SYNTH_NORMAL_TEMPLATES)]
        yield Sample(label="normal", subject=subj, body=body, source="synthetic_normal")


def _iter_synthetic_notifications(n: int = 500) -> Iterable[Sample]:
    for i in range(n):
        subj, body = _SYNTH_NOTIF_TEMPLATES[i % len(_SYNTH_NOTIF_TEMPLATES)]
        yield Sample(
            label="notification",
            subject=subj,
            body=body.format(name="user", id=1000 + i),
            source="synthetic_notifications",
        )


# ============================================================
# Main merge routine
# ============================================================


def _safe_iter(
    label: str,
    iterator_factory: Callable[[], Iterable[Sample]],
) -> list[Sample]:
    """Run an iterator factory and catch any exception, returning a list."""
    try:
        return list(iterator_factory())
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load %s: %s", label, exc)
        return []


def merge_all() -> Path:
    """Build the unified merged dataset CSV. Returns the path."""
    out_path = settings.merged_dataset_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    samples: list[Sample] = []

    # Public datasets
    samples += _safe_iter("enron_normal", lambda: _iter_enron_normal(max_samples=200_000))
    samples += _safe_iter("enron_spam", lambda: _iter_enron_spam(max_samples=50_000))
    samples += _safe_iter("phishing", lambda: _iter_phishing(max_samples=50_000))
    samples += _safe_iter("sms", lambda: _iter_sms(max_samples=10_000))

    # Synthetic fallbacks — always present so classes are never empty
    if not any(s.label == "normal" for s in samples):
        samples += _safe_iter("synthetic_normal", lambda: _iter_synthetic_normal(2000))
    if not any(s.label == "notification" for s in samples):
        samples += _safe_iter("synthetic_notifications", lambda: _iter_synthetic_notifications(2000))
    if not any(s.label == "spam" for s in samples):
        # Add a small synthetic spam set (re-use phishing-style templates)
        for i in range(500):
            samples.append(
                Sample(
                    label="spam",
                    subject="Limited offer just for you",
                    body="Click here to claim your free prize. Act now!",
                    source="synthetic_spam",
                )
            )
    if not any(s.label == "scam" for s in samples):
        for i in range(500):
            samples.append(
                Sample(
                    label="scam",
                    subject="Verify your account immediately",
                    body="Dear customer, click here to verify your account: http://bit.ly/abc",
                    source="synthetic_scam",
                )
            )

    # Persist
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["label", "subject", "body", "source"])
        for s in samples:
            w.writerow([s.label, s.subject, s.body, s.source])

    # Quick stats
    by_class: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for s in samples:
        by_class[s.label] = by_class.get(s.label, 0) + 1
        by_source[s.source] = by_source.get(s.source, 0) + 1

    # If we STILL ended up with very few samples (every public download
    # failed), splice in the in-repo seed data so training has signal.
    if sum(by_class.values()) < 200:
        try:
            from ai_service.app.data.build_seed import build_seed_csv
            build_seed_csv(out_path=out_path)
            logger.warning(
                "Public dataset acquisition returned %d samples; "
                "merged in-repo seed dataset as a fallback.",
                sum(by_class.values()),
            )
            return out_path
        except Exception as exc:  # noqa: BLE001
            logger.error("Seed fallback also failed: %s", exc)

    logger.info("Wrote merged dataset -> %s (%d samples)", out_path, len(samples))
    logger.info("By class: %s", by_class)
    logger.info("By source: %s", by_source)
    return out_path


# ============================================================
# CLI
# ============================================================


def _parse_args() -> dict:
    import argparse

    p = argparse.ArgumentParser(description="Build the merged email dataset")
    p.add_argument("--max-enron", type=int, default=200_000,
                   help="Cap on Enron (corbt) samples to keep")
    p.add_argument("--max-enron-spam", type=int, default=50_000,
                   help="Cap on Enron-spam (bvk) samples")
    p.add_argument("--max-phishing", type=int, default=50_000,
                   help="Cap on phishing samples")
    p.add_argument("--max-sms", type=int, default=10_000,
                   help="Cap on SMS samples")
    p.add_argument("--force-download", action="store_true",
                   help="Re-download raw files even if cached")
    return vars(p.parse_args())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    args = _parse_args()
    # Apply caps by monkey-patching
    from ai_service.scripts import merge_datasets as _self

    _orig_enron = _self._iter_enron_normal
    _orig_enron_spam = _self._iter_enron_spam
    _orig_phishing = _self._iter_phishing
    _orig_sms = _self._iter_sms

    def _capped(fn, n):
        return lambda: fn(max_samples=n) if n is not None else fn()

    _self._iter_enron_normal = _capped(_orig_enron, args["max_enron"])
    _self._iter_enron_spam = _capped(_orig_enron_spam, args["max_enron_spam"])
    _self._iter_phishing = _capped(_orig_phishing, args["max_phishing"])
    _self._iter_sms = _capped(_orig_sms, args["max_sms"])

    if args["force_download"]:
        for d in (settings.datasets_dir / "raw",).iterdir():
            try:
                if d.is_file():
                    d.unlink()
            except Exception:  # noqa: BLE001
                pass

    merge_all()