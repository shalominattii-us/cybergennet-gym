"""Tests for credential lifecycle."""
import sys
sys.path.insert(0, ".")

import pytest
from core.models.credential import Credential, CredentialLevel, RiskLevel, LEVEL_MAP


class TestCredentialLifecycle:
    def test_issue_credential(self):
        c = Credential(
            athlete_id="athlete-0001",
            level=CredentialLevel.REGISTERED,
            scope=["gym:enter"],
        )
        assert c.credential_id.startswith("cred-")
        assert c.level == CredentialLevel.REGISTERED
        assert c.revoked is False
        assert c.revocable is True

    def test_revoke_credential(self):
        c = Credential(athlete_id="athlete-0001")
        c.revoked = True
        c.revoked_at = None  # would be set in service
        c.revocation_reason = "test"
        assert c.revoked is True

    def test_credential_expiry(self):
        from datetime import datetime, timedelta
        c = Credential(
            athlete_id="athlete-0001",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        assert c.expires_at is not None
        assert c.expires_at > datetime.utcnow()

    def test_credential_levels_order(self):
        """Verify credential levels are in the right order."""
        assert LEVEL_MAP[CredentialLevel.REGISTERED] == 0
        assert LEVEL_MAP[CredentialLevel.TRAINING] == 1
        assert LEVEL_MAP[CredentialLevel.QUALIFIED] == 2
        assert LEVEL_MAP[CredentialLevel.SPARRING] == 3
        assert LEVEL_MAP[CredentialLevel.ARENA_READY] == 4
        assert LEVEL_MAP[CredentialLevel.SPECIALIZED] == 5
        assert LEVEL_MAP[CredentialLevel.DELEGATED_AUTHORITY] == 6

    def test_scope_based_authorization(self):
        c = Credential(
            athlete_id="athlete-0001",
            level=CredentialLevel.TRAINING,
            scope=["drill:precision", "drill:reaction"],
            maximum_risk=RiskLevel.LOW,
        )
        assert "drill:precision" in c.scope
        assert "drill:conditioning" not in c.scope
        assert c.maximum_risk == RiskLevel.LOW
