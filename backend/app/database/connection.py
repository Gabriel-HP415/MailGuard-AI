"""SQLAlchemy engine, session factory, and Base class."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""

    pass


engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
    echo=settings.app_debug,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Used in development; Alembic handles production."""
    # Import models so they are registered on Base.metadata.
    from app.models import (  # noqa: F401
        activity_log,
        blacklist,
        email,
        feedback,
        model_version,
        prediction,
        user,
        whitelist,
    )

    Base.metadata.create_all(bind=engine)