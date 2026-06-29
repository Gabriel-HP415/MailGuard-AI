"""Prediction ORM model — output of the AI service for an email."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    DECIMAL,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import EmailClass, ThreatLevel
from app.database.connection import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.email import Email
    from app.models.feedback import Feedback
    from app.models.model_version import ModelVersion
    from app.models.user import User


class Prediction(Base, TimestampMixin):
    """AI prediction result for a single email."""

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("emails.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    model_version_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("model_versions.id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    predicted_class: Mapped[EmailClass] = mapped_column(
        SAEnum(EmailClass, name="email_class", length=20),
        nullable=False,
        index=True,
    )
    class_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    confidence: Mapped[float] = mapped_column(DECIMAL(5, 4), nullable=False)
    risk_score: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    threat_level: Mapped[ThreatLevel] = mapped_column(
        SAEnum(ThreatLevel, name="threat_level", length=20),
        nullable=False,
        default=ThreatLevel.LOW,
    )
    probabilities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    explanation: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    highlighted_spans: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    suspicious_urls: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    inference_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    email: Mapped["Email"] = relationship("Email", back_populates="predictions")
    user: Mapped["User"] = relationship("User", back_populates="predictions")
    model_version: Mapped["ModelVersion"] = relationship("ModelVersion", back_populates="predictions")
    feedback: Mapped[list["Feedback"]] = relationship(
        "Feedback", back_populates="prediction", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Prediction id={self.id} class={self.predicted_class} "
            f"risk={self.risk_score} threat={self.threat_level}>"
        )