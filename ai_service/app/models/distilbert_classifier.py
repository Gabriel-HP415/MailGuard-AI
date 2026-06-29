"""DistilBERT-based email classifier.

Supports:
- Fine-tuning from `distilbert-base-uncased`.
- Saving the trained model + tokenizer to disk.
- Loading back for inference with GPU/CPU auto-detection.
- Probability outputs + latency timing.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from ai_service.app.config import settings
from ai_service.app.constants import CLASS_TO_INDEX, EmailClass
from ai_service.app.preprocessing.text_cleaner import normalize_email

logger = logging.getLogger(__name__)


@dataclass
class DistilBertPrediction:
    """Result of a single DistilBERT prediction."""

    label_index: int
    label_name: str
    confidence: float
    probabilities: np.ndarray
    inference_time_ms: int


class DistilBertClassifier:
    """Wrapper around a fine-tuned DistilBERT model."""

    def __init__(
        self,
        model_name: str | None = None,
        num_labels: int = 4,
        device: str | None = None,
    ):
        self.model_name = model_name or settings.distilbert_model_name
        self.num_labels = num_labels
        self.device = device or settings.inference_device
        self.model = None
        self.tokenizer = None
        self.is_loaded = False

    def load(self, model_dir: Path | str | None = None) -> None:
        """Load model + tokenizer from a directory (or pretrained name)."""
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch

        target = Path(model_dir) if model_dir else None
        if target and target.exists():
            logger.info("Loading DistilBERT from %s", target)
            self.tokenizer = AutoTokenizer.from_pretrained(target)
            self.model = AutoModelForSequenceClassification.from_pretrained(target)
        else:
            logger.info("Loading pretrained DistilBERT %s", self.model_name)
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name, num_labels=self.num_labels
            )

        # Resolve device.
        if self.device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available; falling back to CPU")
            self.device = "cpu"
        self.model.to(self.device)
        self.model.eval()
        self.is_loaded = True

    def save(self, model_dir: Path | str) -> None:
        """Persist model + tokenizer to disk."""
        if not self.is_loaded:
            raise RuntimeError("Model is not loaded")
        p = Path(model_dir)
        p.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(p)
        self.tokenizer.save_pretrained(p)
        logger.info("Saved DistilBERT to %s", p)

    def predict(self, email: dict) -> DistilBertPrediction:
        """Predict the class for a single email dict (subject/body/sender)."""
        if not self.is_loaded:
            raise RuntimeError("Model not loaded; call .load() first")

        import torch

        text = normalize_email(
            subject=email.get("subject"),
            body=email.get("body"),
            sender=email.get("sender"),
        )
        if not text:
            text = "[empty email]"

        inputs = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=settings.max_sequence_length,
            return_tensors="pt",
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        t0 = time.perf_counter()
        with torch.no_grad():
            logits = self.model(**inputs).logits
        probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]
        inference_ms = int((time.perf_counter() - t0) * 1000)

        idx = int(np.argmax(probs))
        return DistilBertPrediction(
            label_index=idx,
            label_name=class_from_index(idx).value,
            confidence=float(probs[idx]),
            probabilities=probs,
            inference_time_ms=inference_ms,
        )

    def predict_batch(self, emails: list[dict]) -> list[DistilBertPrediction]:
        """Predict a batch of emails."""
        return [self.predict(e) for e in emails]


def class_from_index(idx: int) -> EmailClass:
    """Map numeric label back to EmailClass."""
    for cls, i in CLASS_TO_INDEX.items():
        if i == idx:
            return cls
    return EmailClass.NORMAL


def build_training_dataset(
    texts: Iterable[str],
    labels: Iterable[str | int],
    val_split: float | None = None,
    random_seed: int | None = None,
):
    """Convert text + labels into a HuggingFace Dataset (with optional val split)."""
    from datasets import Dataset

    label_ids = [
        CLASS_TO_INDEX[EmailClass(l)] if isinstance(l, str) else int(l) for l in labels
    ]
    data = {"text": list(texts), "label": label_ids}
    ds = Dataset.from_dict(data)
    if val_split is None:
        val_split = settings.train_test_split
    if val_split and val_split > 0:
        split = ds.train_test_split(test_size=val_split, seed=random_seed or settings.random_seed)
        return split["train"], split["test"]
    return ds, None


def train_distilbert(
    train_ds,
    val_ds=None,
    output_dir: Path | str = "models/artifacts/distilbert_finetuned",
    epochs: int | None = None,
    batch_size: int | None = None,
    learning_rate: float | None = None,
) -> dict:
    """Fine-tune DistilBERT and save the artifact. Returns training metrics."""
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        Trainer,
        TrainingArguments,
    )
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
    import numpy as np

    epochs = epochs or settings.epochs
    batch_size = batch_size or settings.batch_size
    learning_rate = learning_rate or settings.learning_rate

    tokenizer = AutoTokenizer.from_pretrained(settings.distilbert_model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        settings.distilbert_model_name, num_labels=4
    )

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=settings.max_sequence_length,
        )

    train_ds = train_ds.map(tokenize, batched=True)
    if val_ds is not None:
        val_ds = val_ds.map(tokenize, batched=True)

    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        return {
            "accuracy": accuracy_score(labels, preds),
            "f1": f1_score(labels, preds, average="weighted", zero_division=0),
            "precision": precision_score(labels, preds, average="weighted", zero_division=0),
            "recall": recall_score(labels, preds, average="weighted", zero_division=0),
        }

    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        learning_rate=learning_rate,
        eval_strategy="epoch" if val_ds is not None else "no",
        save_strategy="epoch",
        load_best_model_at_end=val_ds is not None,
        metric_for_best_model="f1",
        logging_steps=50,
        report_to="none",
        seed=settings.random_seed,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics if val_ds is not None else None,
    )

    trainer.train()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    metrics: dict = {"epochs": epochs, "samples": len(train_ds)}
    if val_ds is not None:
        eval_metrics = trainer.evaluate()
        metrics.update({f"val_{k}": v for k, v in eval_metrics.items()})
    return metrics