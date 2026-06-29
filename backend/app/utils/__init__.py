"""Backend utility helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def utcnow() -> datetime:
    """UTC now (naive, for SQLAlchemy columns without timezone)."""
    return datetime.utcnow()


def serialize_for_json(obj: Any) -> Any:
    """Recursively convert datetime/Enum to JSON-safe types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "value") and callable(obj.value):
        return obj.value
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_for_json(v) for v in obj]
    return obj