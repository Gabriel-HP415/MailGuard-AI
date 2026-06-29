"""Whitelist ORM model — trusted senders per user."""

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Whitelist(Base, TimestampMixin):
    """Trusted senders the user has whitelisted (skipped from spam warnings)."""

    __tablename__ = "whitelist"
    __table_args__ = (
        UniqueConstraint("user_id", "sender", name="uq_whitelist_user_sender"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    )
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="whitelist")

    def __repr__(self) -> str:
        return f"<Whitelist user={self.user_id} sender={self.sender}>"