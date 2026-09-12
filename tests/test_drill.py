"""Tests for drill lifecycle."""
import sys
sys.path.insert(0, ".")

import pytest
from core.models.drill import (
    DrillDefinition, DrillRun, DrillRunMetrics, DrillCapability,
    DrillDifficulty, DrillStatus, GymProgram,
)


class TestDrillLifecycle:
    def test_create_drill(self):
        d = DrillDefinition(
            name="Precision Test",
            capability=DrillCapability.PRECISION,
            difficulty=DrillDifficulty.BASIC,
        )
        assert d.name == "Precision Test"
        assert d.capability == DrillCapability.PRECISION

    def test_drill_run(self):
        r = DrillRun(
            drill_id="DRL-TEST",
            athlete_id="athlete-0001",
            status=DrillStatus.IN_PROGRESS,
        )
        assert r.id.startswith("RUN-")
        assert r.status == DrillStatus.IN_PROGRESS

    def test_drill_run_metrics(self):
        m = DrillRunMetrics(
            raw_score=0.85,
            adjusted_score=0.75,
            recovery_time_ms=1200.0,
            load_impact=0.2,
            fatigue_factor=0.3,
        )
        assert m.raw_score == 0.85
        assert m.adjusted_score == 0.75

    def test_create_program(self):
        p = GymProgram(
            name="Basic Training",
            drill_ids=["DRL-001", "DRL-002"],
            min_score=0.7,
        )
        assert p.name == "Basic Training"
        assert len(p.drill_ids) == 2
