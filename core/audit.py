"""Audit trail helpers - every privileged action lands in ``audit_logs``."""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from .models import AuditLog

logger = logging.getLogger(__name__)


def log_action(db: Session, action: str, *, actor_type: str = "system",
               actor_id: str = "", entity: str = "", entity_id: str = "",
               detail: Optional[dict] = None) -> AuditLog:
    """Append an audit record (caller owns the commit/rollback)."""
    entry = AuditLog(
        action=action,
        actor_type=actor_type,
        actor_id=str(actor_id or ""),
        entity=entity,
        entity_id=str(entity_id or ""),
        detail=detail or {},
    )
    db.add(entry)
    return entry


def log_and_commit(db: Session, action: str, **kwargs) -> None:
    log_action(db, action, **kwargs)
    db.commit()
