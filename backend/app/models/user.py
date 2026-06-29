"""User ORM model."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SAEnum, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import UserRole
from app.database.connection import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.email import Email
    from app.models.feedback import Feedback
    from app.models.prediction import Prediction
    from app.models.blacklist import Blacklist
    from app.models.whitelist import Whitelist


class User(Base, TimestampMixin):
    """Represents a registered user of MailGuard-AI."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", length=20),
        nullable=False,
        default=UserRole.USER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    last_login_at: Mapped[Optional[object]] = mapped_column(DateTime, nullable=True)

    # ---------- Firebase Auth (Chrome extension sign-in) ----------
    # `password_hash` is empty string for Firebase-only users.
    firebase_uid: Mapped[Optional[str]] = mapped_column(
        String(128), unique=True, nullable=True, index=True
    )
    auth_provider: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=False, default="local", server_default="local"
    )

    # Relationships
    emails: Mapped[list["Email"]] = relationship(
        "Email", back_populates="user", cascade="all, delete-orphan"
    )
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="user", cascade="all, delete-orphan"
    )
    feedback: Mapped[list["Feedback"]] = relationship(
        "Feedback", back_populates="user", cascade="all, delete-orphan"
    )
    whitelist: Mapped[list["Whitelist"]] = relationship(
        "Whitelist", back_populates="user", cascade="all, delete-orphan"
    )
    blacklist: Mapped[list["Blacklist"]] = relationship(
        "Blacklist", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role}>"