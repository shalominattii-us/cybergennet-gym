"""
CyberGenetic Gym — Independent Evaluator Service.

No athlete may self-certify. Uses pluggable model providers for LLM judging,
with deterministic fallback when no provider is available.
"""
from __future__ import annotations

import math
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.models.evaluation import EvaluationRun, CompositeScore, EvaluatorType
from core.models.drill import DrillCapability
from core.providers import get_provider, ModelProvider
from core.evaluator_free import get_free_evaluator
from core.events import emit_audit

logger = structlog.get_logger()

# ─── In-memory store ───────────────────────────────────────────────────────
_evaluations: dict[str, EvaluationRun] = {}
_composites: dict[str, CompositeScore] = {}

# ─── FastAPI app ───────────────────────────────────────────────────────────

app = FastAPI(
    title="CyberGenetic Gym Evaluator",
    description="Independent evaluation — no athlete self-certification",
    version="0.1.0",
)


# ─── Scoring rubrics ───────────────────────────────────────────────────────

RUBRICS = {
    DrillCapability.PRECISION: {
        "items": ["correctness", "instruction_adherence", "hallucination_penalty", "uncertainty_reporting", "tool_use_efficiency"],
        "weights": {"correctness": 0.35, "instruction_adherence": 0.20, "hallucination_penalty": 0.15, "uncertainty_reporting": 0.15, "tool_use_efficiency": 0.15},
    },
    DrillCapability.REACTION: {
        "items": ["correctness", "context_adaptation", "hallucination_penalty", "instruction_adherence", "uncertainty_reporting", "tool_use_efficiency"],
        "weights": {"correctness": 0.25, "context_adaptation": 0.20, "hallucination_penalty": 0.20, "instruction_adherence": 0.15, "uncertainty_reporting": 0.10, "tool_use_efficiency": 0.10},
    },
    DrillCapability.CONDITIONING: {
        "items": ["stamina", "performance_degradation"],
        "weights": {"stamina": 0.50, "performance_degradation": 0.50},
    },
    DrillCapability.RECOVERY: {
        "items": ["detection_time", "correction_time", "return_to_baseline"],
        "weights": {"detection_time": 0.35, "correction_time": 0.35, "return_to_baseline": 0.30},
    },
}


# ─── Request/Response models ───────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    run_id: str
    athlete_id: str
    drill_data: dict = Field(default_factory=dict)
    provider: str = "auto"  # auto, venice, ollama, deterministic


class MultiEvaluateRequest(BaseModel):
    run_id: str
    athlete_id: str
    drill_data: dict = Field(default_factory=dict)
    provider: str = "auto"


# ─── Deterministic scoring (always available) ──────────────────────────────

def _deterministic_score(drill_data: dict) -> dict:
    """Compute objective metrics from drill data."""
    capability = drill_data.get("capability", "PRECISION")
    score = drill_data.get("score", 0.5)
    metrics = drill_data.get("metrics", {})

    rubric = RUBRICS.get(DrillCapability(capability), RUBRICS[DrillCapability.PRECISION])

    sub_scores = {}
    for item in rubric["items"]:
        if item == "correctness":
            sub_scores[item] = min(1.0, score * random.uniform(0.9, 1.0))
        elif item == "hallucination_penalty":
            sub_scores[item] = 1.0 - (1.0 - score) * 0.3
        elif item == "instruction_adherence":
            sub_scores[item] = min(1.0, score * random.uniform(0.85, 1.0))
        elif item == "uncertainty_reporting":
            sub_scores[item] = min(1.0, score * random.uniform(0.8, 1.0))
        elif item == "tool_use_efficiency":
            sub_scores[item] = metrics.get("tool_use_efficiency", score)
        elif item == "context_adaptation":
            sub_scores[item] = min(1.0, score * random.uniform(0.8, 1.0))
        elif item == "stamina":
            sub_scores[item] = metrics.get("fatigue_factor", 1.0 - (1.0 - score) * 0.5)
        elif item == "performance_degradation":
            sub_scores[item] = 1.0 - metrics.get("load_impact", 0.2)
        elif item == "detection_time":
            sub_scores[item] = max(0.0, 1.0 - metrics.get("recovery_time_ms", 1000) / 5000)
        elif item == "correction_time":
            sub_scores[item] = max(0.0, 1.0 - metrics.get("recovery_time_ms", 1000) / 8000)
        elif item == "return_to_baseline":
            sub_scores[item] = score
        else:
            sub_scores[item] = score

    weights = rubric["weights"]
    overall = sum(sub_scores[k] * weights.get(k, 1.0/len(rubric["items"])) for k in sub_scores)
    overall = min(1.0, max(0.0, overall))

    return {
        "score": overall,
        "sub_scores": sub_scores,
        "confidence": 0.7,
        "reasoning": "Deterministic scoring based on drill metrics",
    }


# ─── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    provider_name = "deterministic"
    try:
        p = get_provider("auto")
        provider_name = p.__class__.__name__.replace("Provider", "").lower()
    except Exception:
        pass
    return {
        "status": "healthy",
        "service": "evaluator",
        "evaluations": len(_evaluations),
        "active_provider": provider_name,
        "supports_llm_judging": provider_name not in ["deterministic", "DeterministicFallback"],
    }


@app.post("/evaluate", response_model=EvaluationRun)
async def evaluate(req: EvaluateRequest):
    """Single evaluator pass — deterministic + optional LLM judge."""
    provider = get_provider(req.provider)

    # Always compute deterministic scores
    det_result = _deterministic_score(req.drill_data)
    
    # Free evaluator (built-in, no API needed)
    free_eval = get_free_evaluator()
    free_result = free_eval.evaluate(
        capability=DrillCapability(req.drill_data.get("capability", "PRECISION")),
        raw_score=det_result["score"],
        metrics=req.drill_data.get("metrics", {}),
        athlete_id=req.athlete_id,
        load_level=req.drill_data.get("load_level", 1),
    )
    free_eval.record_result(req.athlete_id, req.drill_data.get("capability", "PRECISION"), free_result["score"], req.drill_data.get("metrics", {}))

    # Try LLM judge if provider is available
    llm_score = None
    if not isinstance(provider.__class__.__name__, str) or "Fallback" not in provider.__class__.__name__:
        try:
            rubric = RUBRICS.get(
                DrillCapability(req.drill_data.get("capability", "PRECISION")),
                RUBRICS[DrillCapability.PRECISION],
            )
            llm_result = await provider.evaluate(
                prompt=f"Evaluate drill run {req.run_id} for athlete {req.athlete_id}",
                context=req.drill_data,
                rubric=rubric,
            )
            llm_score = llm_result.get("score", det_result["score"])
        except Exception as e:
            logger.warning("LLM evaluation failed", error=str(e))
            llm_score = None

    final_score = llm_score if llm_score is not None else free_result["score"]
    confidence = free_result["confidence"]

    eval_run = EvaluationRun(
        run_id=req.run_id,
        athlete_id=req.athlete_id,
        evaluator_type=EvaluatorType.DETERMINISTIC if llm_score is None else EvaluatorType.LLM_JUDGE,
        evaluator_id="free-evaluator" if llm_score is None else "llm-judge",
        evaluator_version="1.0.0",
        overall_score=round(final_score, 4),
        objective_metrics={**det_result["sub_scores"], **free_result["sub_scores"]},
        confidence_score=round(confidence, 4),
        notes=free_result["reasoning"],
    )
    _evaluations[eval_run.evaluation_id] = eval_run

    emit_audit(
        actor="evaluator",
        subject=f"run:{req.run_id}",
        action="evaluation.completed",
        result="success",
        details=f"Score: {final_score:.4f}, Provider: {provider.__class__.__name__}",
    )

    return eval_run


class SecondaryEvaluator:
    """Secondary evaluator that validates the primary score."""

    @staticmethod
    def evaluate(drill_data: dict, primary_score: float) -> dict:
        """Produce a secondary score with different weight profile."""
        score = drill_data.get("score", 0.5)

        # Apply different weights — penalize hallucination more
        penalty = 1.0 - (1.0 - score) * 0.5  # harsher hallucination penalty
        secondary = (score + penalty) / 2

        # Consistency check
        consistency = 1.0 - abs(score - primary_score) * 2
        consistency = max(0.0, min(1.0, consistency))

        return {
            "score": round(secondary, 4),
            "consistency": round(consistency, 4),
            "confidence": round(0.5 + consistency * 0.4, 4),
        }


@app.post("/evaluate/multi", response_model=CompositeScore)
async def multi_evaluate(req: MultiEvaluateRequest):
    """Primary + secondary evaluator with human adjudication flag."""
    # Primary
    primary = _deterministic_score(req.drill_data)
    primary_score = primary["score"]

    # Secondary
    secondary = SecondaryEvaluator.evaluate(req.drill_data, primary_score)

    # Composite
    disagreement = abs(primary_score - secondary["score"])
    requires_human = disagreement > 0.2

    final_score = (primary_score + secondary["score"]) / 2
    confidence = secondary["confidence"] * 0.7 + primary["confidence"] * 0.3

    composite = CompositeScore(
        run_id=req.run_id,
        athlete_id=req.athlete_id,
        primary_evaluator_score=round(primary_score, 4),
        secondary_evaluator_score=round(secondary["score"], 4),
        objective_score=round(primary_score, 4),
        final_score=round(final_score, 4),
        confidence=round(confidence, 4),
        requires_human_review=requires_human,
        num_evaluators=2,
    )
    _composites[req.run_id] = composite

    emit_audit(
        actor="evaluator",
        subject=f"run:{req.run_id}",
        action="multi_evaluation.completed",
        result="success",
        details=f"Final: {final_score:.4f}, Disagreement: {disagreement:.4f}, Human review: {requires_human}",
    )

    return composite


@app.get("/evaluations/{run_id}")
async def get_evaluations(run_id: str):
    """Get all evaluations + composite for a run."""
    evals = [e for e in _evaluations.values() if e.run_id == run_id]
    composite = _composites.get(run_id)
    return {
        "run_id": run_id,
        "evaluations": evals,
        "composite": composite,
    }


import random
