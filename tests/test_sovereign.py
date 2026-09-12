"""Tests for SovereignOS integration service."""
import sys
sys.path.insert(0, ".")

import pytest
from core.models.sovereign import (
    SovereignPolicy, GovernanceGate, GovernanceDecision,
    SovereignLedgerEntry, PolicyDomain, PolicyAction,
)


class TestSovereign:
    def test_create_policy(self):
        p = SovereignPolicy(
            domain=PolicyDomain.SECURITY,
            resource="genetic:mutate_constitutional",
            action=PolicyAction.DENY,
        )
        assert p.policy_id.startswith("pol-")
        assert p.active is True

    def test_default_deny_policy(self):
        p = SovereignPolicy(
            domain=PolicyDomain.TREASURY,
            resource="treasury:live_execution",
            action=PolicyAction.DENY,
        )
        assert p.action == PolicyAction.DENY

    def test_require_approval_policy(self):
        p = SovereignPolicy(
            domain=PolicyDomain.CREDENTIAL,
            resource="credential:issue:level_6",
            action=PolicyAction.REQUIRE_APPROVAL,
        )
        assert p.action == PolicyAction.REQUIRE_APPROVAL
        assert p.priority == 100

    def test_governance_gate(self):
        g = GovernanceGate(name="Main Gate", policy_ids=["pol-1", "pol-2"])
        assert g.gate_id.startswith("gate-")
        assert g.auto_approve_level == 6

    def test_governance_decision(self):
        d = GovernanceDecision(
            athlete_id="athlete-1",
            action="enter",
            resource="arena:enter",
            decision=PolicyAction.ALLOW,
        )
        assert d.decision == PolicyAction.ALLOW
        assert d.requires_human is False

    def test_ledger_entry(self):
        e = SovereignLedgerEntry(
            source="gym",
            event_type="drill.completed",
            athlete_id="athlete-1",
            details={"drill_id": "drill-1", "score": 0.85},
        )
        assert e.entry_id.startswith("ledger-")
        assert e.synced_to_sovereign is False
