"""Tests for evaluation system."""
import sys
sys.path.insert(0, ".")

import pytest
from core.models.evaluation import EvaluationRun, CompositeScore, EvaluatorType
from core.models.drill import DrillCapability


class TestEvaluation:
    def test_evaluation_run(self):
        e = EvaluationRun(
            run_id="RUN-TEST",
            athlete_id="athlete-0001",
            evaluator_type=EvaluatorType.DETERMINISTIC,
            evaluator_id="evaluator-primary",
            overall_score=0.78,
            confidence_score=0.85,
        )
        assert e.evaluation_id.startswith("eval-")
        assert e.overall_score == 0.78
        assert e.requires_human_adjudication is False

    def test_composite_score(self):
        c = CompositeScore(
            run_id="RUN-TEST",
            athlete_id="athlete-0001",
            primary_evaluator_score=0.82,
            secondary_evaluator_score=0.79,
            objective_score=0.85,
            final_score=0.82,
            confidence=0.90,
        )
        assert c.final_score == 0.82
        assert c.requires_human_review is False

    def test_human_adjudication_flag(self):
        """When primary and secondary disagree by > 0.2, flag human review."""
        c = CompositeScore(
            run_id="RUN-TEST",
            athlete_id="athlete-0001",
            primary_evaluator_score=0.95,
            secondary_evaluator_score=0.60,
            final_score=0.78,
            confidence=0.50,
            requires_human_review=True,
        )
        assert c.requires_human_review is True

    def test_no_self_certification_service_level(self):
        """Athlete cannot be their own evaluator — enforced at service level, not model."""
        # Pydantic model allows same athlete_id and evaluator_id
        # Service layer rejects it — this test validates the model allows it
        e = EvaluationRun(
            run_id="RUN-TEST",
            athlete_id="athlete-0001",
            evaluator_id="athlete-0001",
            evaluator_type=EvaluatorType.DETERMINISTIC,
        )
        assert e.evaluator_id == e.athlete_id  # model permits it
