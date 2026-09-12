"""Tests for genetic engine."""
import sys
sys.path.insert(0, ".")

import pytest
from core.models.genetic import Generation, FitnessScore, GeneticOperation, GeneticOperationRecord
from core.models.athlete import TraitManifest
from core.constitutional import CONSTITUTIONAL_FIELDS, ADAPTIVE_FIELDS


class TestGeneticEngine:
    def test_generation_creation(self):
        g = Generation(
            number=0,
            population_ids=["athlete-0001"],
        )
        assert g.generation_id.startswith("gen-")
        assert g.number == 0

    def test_fitness_score_defaults(self):
        """Composite score is 0 by default — calculated by service."""
        f = FitnessScore(
            athlete_id="athlete-0001",
            generation=0,
            fitness=0.85,
            novelty=0.60,
            robustness=0.75,
            recovery_score=0.70,
        )
        # composite_score is a regular field, defaults to 0.0
        assert f.composite_score == 0.0
        assert f.ranked is False

    def test_genetic_operation_record(self):
        r = GeneticOperationRecord(
            generation=0,
            operation=GeneticOperation.SELECTION,
            parent_ids=["athlete-0001"],
            child_ids=["athlete-0002"],
        )
        assert r.operation == GeneticOperation.SELECTION

    def test_constitutional_vs_adaptive_separation(self):
        """Verify no overlap between constitutional and adaptive fields."""
        overlap = CONSTITUTIONAL_FIELDS & ADAPTIVE_FIELDS
        assert len(overlap) == 0, f"Fields overlap: {overlap}"
        assert "precision" in ADAPTIVE_FIELDS
        assert "security_policy_version" in CONSTITUTIONAL_FIELDS

    def test_trait_manifest_adaptive_only(self):
        """TraitManifest should only contain adaptive fields."""
        t = TraitManifest()
        trait_keys = set(t.model_dump().keys())
        assert "precision" in trait_keys
        assert "recovery" in trait_keys
        assert "security_policy_version" not in trait_keys
        assert "audit_required" not in trait_keys
