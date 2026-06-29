"""Activity log service — audit trail."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.user import User


def log(
    db: Session,
    *,
    user: Optional[User],
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    status: str = "success",
    details: dict[str, Any] | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        details=details,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry