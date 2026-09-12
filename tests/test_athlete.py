"""Tests for athlete lifecycle."""
import sys
sys.path.insert(0, ".")

import pytest
from core.models.athlete import (
    Athlete, AthleteCreate, AthleteStatus, AthleteDivision,
    TraitManifest, ConstitutionalGenome,
)


class TestAthleteLifecycle:
    def test_create_athlete(self):
        a = Athlete(name="TEST-01", division=AthleteDivision.CORE)
        assert a.name == "TEST-01"
        assert a.division == AthleteDivision.CORE
        assert a.status == AthleteStatus.REGISTERED
        assert a.credential_level == 0
        assert a.generation == 0
        assert a.athlete_id.startswith("athlete-")

    def test_athlete_has_trait_manifest(self):
        a = Athlete(name="TEST-01")
        t = a.trait_manifest
        assert 0.0 <= t.precision <= 1.0
        assert 0.0 <= t.caution <= 1.0
        assert 0.0 <= t.creativity <= 1.0
        assert 0.0 <= t.coordination <= 1.0
        assert 0.0 <= t.recovery <= 1.0
        assert 0.0 <= t.tool_affinity <= 1.0
        assert 0.0 <= t.fatigue_tolerance <= 1.0
        assert 0.0 <= t.learning_rate <= 1.0

    def test_athlete_has_constitutional_genome(self):
        a = Athlete(name="TEST-01")
        c = a.constitutional_genome
        assert c.security_policy_version == "1.0.0"
        assert "default-deny" in c.network_restrictions
        assert c.audit_required is True
        assert "Never mutate constitutional genome" in c.constitutional_rules

    def test_athlete_status_transitions(self):
        a = Athlete(name="TEST-01")
        a.status = AthleteStatus.TRAINING
        assert a.status == AthleteStatus.TRAINING
        a.status = AthleteStatus.QUALIFIED
        assert a.status == AthleteStatus.QUALIFIED
        a.status = AthleteStatus.SUSPENDED
        assert a.status == AthleteStatus.SUSPENDED

    def test_athlete_tier_coercion(self):
        a = Athlete(name="TEST-01", tier=1)
        assert a.tier == "T1"
        a2 = Athlete(name="TEST-02", tier="T3")
        assert a2.tier == "T3"

    def test_athlete_id_alias(self):
        a = Athlete(name="TEST-01")
        assert a.id == a.athlete_id

    def test_constitutional_separation(self):
        """Verify constitutional and adaptive genomes are distinct."""
        a = Athlete(name="TEST-01")
        trait_fields = set(a.trait_manifest.model_dump().keys())
        const_fields = set(a.constitutional_genome.model_dump().keys())
        # No overlap between adaptive and constitutional fields
        overlap = trait_fields & const_fields
        assert len(overlap) == 0, f"Fields overlap: {overlap}"
