"""Tests for constitutional genome immutability."""
import sys
sys.path.insert(0, ".")

import pytest
from core.models.athlete import Athlete, ConstitutionalGenome
from core.constitutional import (
    verify_constitutional_integrity,
    extract_constitutional_hash,
    CONSTITUTIONAL_FIELDS,
)


class TestConstitutionalImmutability:
    def test_constitutional_integrity_check(self):
        a = Athlete(name="TEST-01")
        original = a.constitutional_genome
        current = original.model_dump()
        assert verify_constitutional_integrity(original, current) is True

    def test_constitutional_violation_detected(self):
        a = Athlete(name="TEST-01")
        original = a.constitutional_genome
        current = original.model_dump()
        # Simulate a mutation attempt
        current["security_policy_version"] = "0.0.0-evil"
        assert verify_constitutional_integrity(original, current) is False

    def test_constitutional_hash_stable(self):
        c1 = ConstitutionalGenome()
        c2 = ConstitutionalGenome()
        # Same defaults should produce same hash
        h1 = extract_constitutional_hash(c1)
        h2 = extract_constitutional_hash(c2)
        assert h1 == h2

    def test_modified_constitutional_hash_changes(self):
        c1 = ConstitutionalGenome()
        h1 = extract_constitutional_hash(c1)
        c2 = ConstitutionalGenome()
        c2.audit_required = False
        h2 = extract_constitutional_hash(c2)
        assert h1 != h2

    def test_audit_event_on_violation(self):
        """Verify audit event fields are present for violation tracking."""
        from core.events import emit_audit
        event = emit_audit(
            actor="genetic-engine",
            subject="constitutional-genome",
            action="CONSTITUTIONAL_VIOLATION_ATTEMPT",
            result="denied",
            details="Attempted to mutate security_policy_version",
        )
        assert event.action == "CONSTITUTIONAL_VIOLATION_ATTEMPT"
        assert event.result == "denied"
