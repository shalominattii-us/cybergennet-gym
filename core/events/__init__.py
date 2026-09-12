"""
Audit event system — every state-changing action produces an immutable-style event.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """Every meaningful state-changing action produces one of these."""

    event_id: str = Field(default_factory=lambda: f"audit-{uuid.uuid4().hex[:12]}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: str
    subject: str
    action: str
    result: str
    details: Optional[str] = None
    policy_version: str = "1.0.0"
    environment_hash: str = ""
    provenance_hash: str = ""


def emit_audit(
    actor: str,
    subject: str,
    action: str,
    result: str,
    details: str | None = None,
    policy_version: str = "1.0.0",
) -> AuditEvent:
    """Create and return an audit event (to be persisted by caller)."""
    return AuditEvent(
        actor=actor,
        subject=subject,
        action=action,
        result=result,
        details=details,
        policy_version=policy_version,
    )
