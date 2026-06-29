"""AI Service configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """AI Service settings."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    ai_service_host: str = "0.0.0.0"
    ai_service_port: int = 8001
    log_level: str = "INFO"

    # Paths
    ai_service_root: Path = Path(__file__).resolve().parents[1]
    models_dir: Path = Path(__file__).resolve().parents[1] / "models" / "artifacts"
    datasets_dir: Path = Path(__file__).resolve().parents[1] / "datasets"
    merged_dataset_path: Path = Path(__file__).resolve().parents[1] / "datasets" / "merged_dataset.csv"

    # Model
    distilbert_model_name: str = "distilbert-base-uncased"
    max_sequence_length: int = 256
    active_model_version: str = "auto"
    baseline_model: str = "distilbert"  # naive_bayes | svm | random_forest | distilbert

    # Training
    epochs: int = 3
    batch_size: int = 16
    learning_rate: float = 2e-5
    train_test_split: float = 0.2
    random_seed: int = 42

    # Inference
    inference_device: str = "cpu"  # cpu | cuda
    risk_thresholds_critical: float = 75.0
    risk_thresholds_high: float = 50.0
    risk_thresholds_medium: float = 25.0

    def ensure_dirs(self) -> None:
        """Create the on-disk folders if they don't exist."""
        for d in (self.models_dir, self.datasets_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s


settings = get_settings()