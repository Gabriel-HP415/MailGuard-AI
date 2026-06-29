"""Training scripts for MailGuard-AI AI Service."""

from ai_service.scripts.merge_datasets import merge_all
from ai_service.scripts.train_baseline import train_and_save
from ai_service.scripts.train_distilbert import train

__all__ = ["merge_all", "train_and_save", "train"]