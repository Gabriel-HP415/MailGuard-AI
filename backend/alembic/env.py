"""Alembic environment configuration."""

from logging.config import fileConfig
import socket
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# App config (relative path to backend/)
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.core.config import settings  # noqa: E402
from app.database.connection import Base  # noqa: E402
from app.models import (  # noqa: E402,F401
    ActivityLog,
    Blacklist,
    Email,
    Feedback,
    ModelVersion,
    Prediction,
    User,
    Whitelist,
)

config = context.config
config.set_main_option("sqlalchemy.url", settings.sqlalchemy_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _pg_connect_args(url: str) -> dict:
    """Same IPv4 hostaddr trick as ``app.database.connection``.

    Alembic uses its own ``engine_from_config`` path, so we have to inject
    ``connect_args`` manually via ``sqlalchemy.connect_args`` in config
    below.
    """
    if not (url.startswith("postgresql://") or url.startswith("postgresql+")):
        return {}
    from sqlalchemy.engine.url import make_url

    u = make_url(url)
    host = u.host
    if not host or host == "localhost" or host.startswith("/"):
        return {"connect_args": {"connect_timeout": 10}}
    try:
        infos = socket.getaddrinfo(host, u.port or 5432, socket.AF_INET)
        if infos:
            return {"connect_args": {"connect_timeout": 10, "hostaddr": infos[0][4][0]}}
    except socket.gaierror:
        pass
    return {"connect_args": {"connect_timeout": 10}}


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    section = config.get_section(config.config_ini_section, {})
    url = section.get("sqlalchemy.url", settings.sqlalchemy_url)
    section.update(_pg_connect_args(url))

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()