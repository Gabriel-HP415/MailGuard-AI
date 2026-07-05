"""Feedback ORM model — user feedback for AI predictions (Human-in-the-loop)."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum as SAEnum,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import EmailClass
from app.database.connection import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.prediction import Prediction
    from app.models.user import User


class Feedback(Base, TimestampMixin):
    """User-provided feedback on a prediction (correct / wrong + optional class)."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("predictions.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    correct_class: Mapped[Optional[EmailClass]] = mapped_column(
        SAEnum(
            EmailClass,
            name="correct_class",
            length=20,
            values_callable=lambda enum: [e.value for e in enum],
        ),
        nullable=True,
    )
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    prediction: Mapped["Prediction"] = relationship("Prediction", back_populates="feedback")
    user: Mapped["User"] = relationship("User", back_populates="feedback")

    def __repr__(self) -> str:
        return (
            f"<Feedback id={self.id} prediction_id={self.prediction_id} "
            f"correct={self.is_correct}>"
        )