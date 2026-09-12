"""
SovereignOS integration models — governance gate, policy sync, constitution.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PolicyDomain(str, Enum):
    SECURITY = "security"
    CREDENTIAL = "credential"
    TREASURY = "treasury"
    NETWORK = "network"
    EVALUATION = "evaluation"
    GENETIC = "genetic"
    ARENA = "arena"


class PolicyAction(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ESCALATE = "ESCALATE"


class SovereignPolicy(BaseModel):
    """A policy issued by SovereignOS."""

    policy_id: str = Field(default_factory=lambda: "pol-" + uuid.uuid4().hex[:8])
    domain: PolicyDomain
    resource: str
    action: PolicyAction
    condition: str = ""
    priority: int = 100
    policy_version: str = "1.0.0"
    issued_by: str = "sovereign-os"
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    active: bool = True


class GovernanceGate(BaseModel):
    """
    The gate between SovereignOS and the Gym.

    Every action that crosses this boundary is:
    1. Checked against SovereignOS policy
    2. Logged to the sovereign ledger
    3. Subject to human override
    """

    gate_id: str = Field(default_factory=lambda: "gate-" + uuid.uuid4().hex[:8])
    name: str
    policy_ids: list[str] = Field(default_factory=list)
    required_approvals: int = 1
    auto_approve_level: int = 6
    audit_all: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GovernanceDecision(BaseModel):
    """Result of a governance gate check."""

    decision_id: str = Field(default_factory=lambda: "dec-" + uuid.uuid4().hex[:8])
    athlete_id: str
    action: str
    resource: str
    decision: PolicyAction
    matched_policy_id: str = ""
    requires_human: bool = False
    human_approved: bool = False
    decided_at: datetime = Field(default_factory=datetime.utcnow)


class SovereignLedgerEntry(BaseModel):
    """An entry in the sovereign ledger — cross-system audit trail."""

    entry_id: str = Field(default_factory=lambda: "ledger-" + uuid.uuid4().hex[:8])
    source: str
    event_type: str
    athlete_id: str = ""
    details: dict = Field(default_factory=dict)
    policy_version: str = ""
    provenance_hash: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    synced_to_sovereign: bool = False
    synced_at: Optional[datetime] = None
