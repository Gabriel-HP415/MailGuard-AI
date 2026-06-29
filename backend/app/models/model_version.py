"""ModelVersion ORM model — registry of AI model versions."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DECIMAL,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.prediction import Prediction


class ModelVersion(Base, TimestampMixin):
    """A specific trained model artifact (for tracking & rollback)."""

    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    accuracy: Mapped[Optional[float]] = mapped_column(DECIMAL(5, 4), nullable=True)
    precision_score: Mapped[Optional[float]] = mapped_column(DECIMAL(5, 4), nullable=True)
    recall: Mapped[Optional[float]] = mapped_column(DECIMAL(5, 4), nullable=True)
    f1_score: Mapped[Optional[float]] = mapped_column(DECIMAL(5, 4), nullable=True)
    training_samples: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    training_duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    # Relationships
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="model_version"
    )

    def __repr__(self) -> str:
        return f"<ModelVersion {self.version} active={self.is_active}>"