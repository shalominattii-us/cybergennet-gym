"""
SovereignOS Integration Service — governance gate between Gym and SovereignOS.

Every cross-boundary action is:
1. Checked against SovereignOS policy
2. Logged to the sovereign ledger
3. Subject to human override
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException

from core.models.sovereign import (
    SovereignPolicy, GovernanceGate, GovernanceDecision,
    SovereignLedgerEntry, PolicyDomain, PolicyAction,
)
from core.events import emit_audit

# ─── In-memory store ───────────────────────────────────────────────────────
_policies: dict[str, SovereignPolicy] = {}
_gates: dict[str, GovernanceGate] = {}
_ledger: list[SovereignLedgerEntry] = []
_decisions: list[GovernanceDecision] = []

# ─── FastAPI app ───────────────────────────────────────────────────────────

app = FastAPI(
    title="SovereignOS Integration",
    description="Governance gate between SovereignOS and CyberGenetic Gym",
    version="0.1.0",
)


# ─── Seed default policies ─────────────────────────────────────────────────

def _seed_policies():
    if _policies:
        return

    defaults = [
        SovereignPolicy(
            domain=PolicyDomain.SECURITY,
            resource="constitutional_genome:*",
            action=PolicyAction.DENY,
            condition="genetic_engine_only",
            priority=1,
        ),
        SovereignPolicy(
            domain=PolicyDomain.CREDENTIAL,
            resource="credential:issue:level_6",
            action=PolicyAction.REQUIRE_APPROVAL,
            priority=10,
        ),
        SovereignPolicy(
            domain=PolicyDomain.TREASURY,
            resource="treasury:live_execution",
            action=PolicyAction.DENY,
            condition="until_g12_clearance",
            priority=1,
        ),
        SovereignPolicy(
            domain=PolicyDomain.EVALUATION,
            resource="evaluation:self_certify",
            action=PolicyAction.DENY,
            priority=1,
        ),
        SovereignPolicy(
            domain=PolicyDomain.GENETIC,
            resource="genetic:mutate_constitutional",
            action=PolicyAction.DENY,
            priority=1,
        ),
        SovereignPolicy(
            domain=PolicyDomain.NETWORK,
            resource="network:egress",
            action=PolicyAction.DENY,
            priority=1,
        ),
        SovereignPolicy(
            domain=PolicyDomain.ARENA,
            resource="arena:enter",
            action=PolicyAction.ALLOW,
            condition="credential_level >= 4",
            priority=50,
        ),
        SovereignPolicy(
            domain=PolicyDomain.TREASURY,
            resource="treasury:simulation",
            action=PolicyAction.ALLOW,
            priority=50,
        ),
    ]

    for p in defaults:
        _policies[p.policy_id] = p

    # Create default governance gate
    gate = GovernanceGate(
        name="Sovereign-Gym Gate",
        policy_ids=list(_policies.keys()),
    )
    _gates[gate.gate_id] = gate


# ─── Policy endpoints ──────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "sovereign-os-integration",
        "policies": len(_policies),
        "gates": len(_gates),
        "ledger_entries": len(_ledger),
    }


@app.get("/policies")
async def list_policies(domain: Optional[str] = None):
    if domain:
        return [p for p in _policies.values() if p.domain.value == domain]
    return list(_policies.values())


@app.post("/policies")
async def create_policy(policy: SovereignPolicy):
    _policies[policy.policy_id] = policy
    emit_audit(
        actor="sovereign-os",
        subject=f"policy:{policy.policy_id}",
        action="policy.created",
        result="success",
        details=f"Domain: {policy.domain.value}, Resource: {policy.resource}",
    )
    return policy


@app.get("/policies/{policy_id}")
async def get_policy(policy_id: str):
    p = _policies.get(policy_id)
    if not p:
        raise HTTPException(404, f"Policy {policy_id} not found")
    return p


@app.post("/policies/{policy_id}/toggle")
async def toggle_policy(policy_id: str):
    p = _policies.get(policy_id)
    if not p:
        raise HTTPException(404, f"Policy {policy_id} not found")
    p.active = not p.active
    return p


# ─── Governance Gate endpoints ─────────────────────────────────────────────

@app.post("/gate/check")
async def check_gate(
    athlete_id: str,
    action: str,
    resource: str,
    credential_level: int = 0,
):
    """Check if an action is allowed through the governance gate."""
    # Find matching policies
    for policy in _policies.values():
        if not policy.active:
            continue
        if resource.startswith(policy.resource.replace("*", "")):
            # Check conditions
            if policy.condition:
                if "credential_level >=" in policy.condition:
                    required = int(policy.condition.split(">= ")[1])
                    if credential_level < required:
                        continue

            decision = GovernanceDecision(
                athlete_id=athlete_id,
                action=action,
                resource=resource,
                decision=policy.action,
                matched_policy_id=policy.policy_id,
                requires_human=policy.action == PolicyAction.REQUIRE_APPROVAL,
            )
            _decisions.append(decision)

            emit_audit(
                actor=athlete_id,
                subject=f"gate:{resource}",
                action=f"gate.check.{policy.action.value}",
                result="allowed" if policy.action == PolicyAction.ALLOW else "denied",
            )

            return decision

    # Default deny
    decision = GovernanceDecision(
        athlete_id=athlete_id,
        action=action,
        resource=resource,
        decision=PolicyAction.DENY,
        requires_human=False,
    )
    _decisions.append(decision)
    return decision


# ─── Sovereign Ledger ──────────────────────────────────────────────────────

@app.post("/ledger")
async def record_ledger_entry(entry: SovereignLedgerEntry):
    _ledger.append(entry)
    return entry


@app.get("/ledger")
async def get_ledger(limit: int = 100, source: Optional[str] = None):
    entries = _ledger
    if source:
        entries = [e for e in entries if e.source == source]
    return entries[-limit:]


@app.get("/ledger/{entry_id}")
async def get_ledger_entry(entry_id: str):
    for e in _ledger:
        if e.entry_id == entry_id:
            return e
    raise HTTPException(404, f"Ledger entry {entry_id} not found")


# ─── Seed on startup ───────────────────────────────────────────────────────

_seed_policies()
