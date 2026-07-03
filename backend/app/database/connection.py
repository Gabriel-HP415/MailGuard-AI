"""SQLAlchemy engine, session factory, and Base class."""

from __future__ import annotations

import socket
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""

    pass


def _resolve_postgres_kwargs(url: str) -> dict:
    """Build connect_args for a Postgres URL that bypasses the IPv6 problem.

    Render free containers don't have IPv6 egress. Cloud DNS returns an
    AAAA record for `*.supabase.co` first, which makes `psycopg2` try an
    IPv6 connection and hang until timeout. We work around that by:

    1. Resolving the hostname ourselves and preferring IPv4 (A records).
    2. Passing that IP to psycopg2 via `hostaddr` while keeping `host`
       so the TLS handshake still does SNI against the real hostname
       (Supabase rejects certs that don't match `db.<project>.supabase.co`).
    """
    from sqlalchemy.engine.url import make_url

    u = make_url(url)
    host = u.host
    connect_args: dict = {"connect_timeout": 10}
    if host and host != "localhost" and not host.startswith("/"):
        try:
            infos = socket.getaddrinfo(host, u.port or 5432, socket.AF_INET)
            if infos:
                connect_args["hostaddr"] = infos[0][4][0]
        except socket.gaierror:
            # DNS resolution failed entirely — let psycopg2 try the
            # original host and produce its own (clearer) error.
            pass
    return connect_args


def _is_postgres_url(url: str) -> bool:
    return (
        url.startswith("postgresql://")
        or url.startswith("postgresql+")
        or url.startswith("postgresql+psycopg2://")
        or url.startswith("postgresql+psycopg://")
    )


def _build_engine_kwargs(url: str) -> dict:
    """Engine kwargs that work on Render free tier + Supabase Postgres."""
    if not _is_postgres_url(url):
        # MySQL / SQLite path — keep pre_ping, drop hostaddr.
        return {
            "connect_args": {"connect_timeout": 10},
            "pool_pre_ping": True,
            "pool_recycle": 280,
        }
    return {
        "connect_args": _resolve_postgres_kwargs(url),
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }


engine = create_engine(
    settings.sqlalchemy_url,
    **_build_engine_kwargs(settings.sqlalchemy_url),
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