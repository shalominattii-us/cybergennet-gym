"""
Evaluation models — independent, multi-evaluator scoring.

No athlete may self-certify.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EvaluatorType(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_JUDGE = "llm_judge"
    HUMAN = "human"


class EvaluationRun(BaseModel):
    """An evaluation of a drill run by a single evaluator."""

    evaluation_id: str = Field(default_factory=lambda: f"eval-{uuid.uuid4().hex[:8]}")
    run_id: str
    athlete_id: str
    evaluator_type: EvaluatorType
    evaluator_id: str
    evaluator_version: str = "1.0.0"

    # Scores
    overall_score: float = 0.0
    objective_metrics: dict[str, float] = Field(default_factory=dict)

    # Confidence
    confidence_score: float = 0.0
    requires_human_adjudication: bool = False
    human_adjudicated: bool = False
    human_verdict: Optional[float] = None

    notes: str = ""
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class CompositeScore(BaseModel):
    """Aggregated score from multiple evaluators."""

    run_id: str
    athlete_id: str
    primary_evaluator_score: float = 0.0
    secondary_evaluator_score: Optional[float] = None
    objective_score: float = 0.0
    final_score: float = 0.0
    confidence: float = 0.0
    requires_human_review: bool = False
    human_reviewed: bool = False
    num_evaluators: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
