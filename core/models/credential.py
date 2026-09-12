"""
Credential model — gated, scoped, revocable credentials for athletes.

Credential ≠ trust.
Authentication ≠ authorization.
Authorization ≠ correctness.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CredentialLevel(str, Enum):
    REGISTERED = "REGISTERED"          # 0 — can enter the Gym
    TRAINING = "TRAINING"              # 1 — can execute sandboxed drills
    QUALIFIED = "QUALIFIED"            # 2 — demonstrated baseline reliability
    SPARRING = "SPARRING"              # 3 — can interact with other agents
    ARENA_READY = "ARENA_READY"        # 4 — can participate in competitive events
    SPECIALIZED = "SPECIALIZED"        # 5 — can receive narrowly scoped tools
    DELEGATED_AUTHORITY = "DELEGATED_AUTHORITY"  # 6 — bounded operational authority


LEVEL_MAP = {
    CredentialLevel.REGISTERED: 0,
    CredentialLevel.TRAINING: 1,
    CredentialLevel.QUALIFIED: 2,
    CredentialLevel.SPARRING: 3,
    CredentialLevel.ARENA_READY: 4,
    CredentialLevel.SPECIALIZED: 5,
    CredentialLevel.DELEGATED_AUTHORITY: 6,
}


class RiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Credential(BaseModel):
    """A scoped, revocable credential."""

    credential_id: str = Field(default_factory=lambda: f"cred-{uuid.uuid4().hex[:12]}")
    athlete_id: str
    level: CredentialLevel = CredentialLevel.REGISTERED
    scope: list[str] = Field(default_factory=list)
    maximum_risk: RiskLevel = RiskLevel.NONE
    issued_by: str = "system"
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    evidence_hash: str = ""
    revocable: bool = True
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None


class CredentialEvent(BaseModel):
    """Audit trail for credential operations."""

    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: str
    subject: str  # athlete_id
    action: str   # issued | revoked | expired | verified
    result: str
    credential_id: str
    policy_version: str = "1.0.0"
    environment_hash: str = ""
    provenance_hash: str = ""
