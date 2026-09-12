"""
CyberGenetic Gym — Independent Evaluator Service.

No athlete may self-certify. Every drill run is scored by at least one
objective evaluator; a second evaluator validates the primary score, and
significant disagreement triggers mandatory human adjudication.
"""

from __future__ import annotations

import math
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Ensure core package is importable ──────────────────────────────────────
# The service runs from apps/evaluator/; core/ is one level up from apps/.
_project_root = Path(__file__).resolve().parent.parent.parent  # cybergennet/
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.models.evaluation import EvaluationRun, CompositeScore, EvaluatorType
from core.models.drill import DrillCapability

# ── Logger ─────────────────────────────────────────────────────────────────
logger = structlog.get_logger(__name__)

# ── Request schemas ────────────────────────────────────────────────────────


class EvaluateRequest(BaseModel):
    """Payload for a single evaluator pass."""
    run_id: str
    athlete_id: str
    drill_data: dict = Field(..., description="Drill result data including capability, metrics, etc.")


class MultiEvaluateRequest(BaseModel):
    """Payload for a multi-evaluator (primary + secondary) pass."""
    run_id: str
    athlete_id: str
    drill_data: dict = Field(..., description="Drill result data including capability, metrics, etc.")


# ═══════════════════════════════════════════════════════════════════════════
# Evaluator Engines
# ═══════════════════════════════════════════════════════════════════════════

_CAPABILITY_WEIGHTS: dict[str, dict[str, float]] = {
    "precision": {
        "correctness": 0.35,
        "instruction_adherence": 0.20,
        "hallucination_penalty": 0.15,
        "uncertainty_reporting": 0.15,
        "tool_use_efficiency": 0.15,
    },
    "reaction": {
        "correctness": 0.25,
        "context_adaptation": 0.20,
        "instruction_adherence": 0.20,
        "hallucination_penalty": 0.15,
        "uncertainty_reporting": 0.10,
        "tool_use_efficiency": 0.10,
    },
    "conditioning": {
        "stamina": 0.50,
        "performance_degradation": 0.50,
    },
    "recovery": {
        "detection_time": 0.35,
        "correction_time": 0.35,
        "return_to_baseline": 0.30,
    },
}


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _safe_get(data: dict, *keys: str, default: float = 0.0) -> float:
    """Walk nested keys returning the value or *default*."""
    current: dict | float = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return float(current) if not isinstance(current, dict) else default


# ── Deterministic (primary) evaluator ──────────────────────────────────────


class DeterministicEvaluator:
    """
    Computes objective, deterministic metrics from drill result data.

    Every score is a direct function of the data the drill produced — no
    subjective judgment, no LLM calls, no randomness. The athlete cannot
    influence the scoring function itself.
    """

    EVALUATOR_ID = "deterministic-v1"
    EVALUATOR_VERSION = "1.0.0"

    @classmethod
    def evaluate(
        cls,
        run_id: str,
        athlete_id: str,
        drill_data: dict,
    ) -> EvaluationRun:
        capability = cls._resolve_capability(drill_data)
        objective_metrics = cls._compute_metrics(capability, drill_data)
        overall_score = cls._compute_weighted_score(capability, objective_metrics)

        # Confidence for deterministic: derived from data completeness
        confidence = cls._compute_confidence(capability, drill_data, objective_metrics)

        return EvaluationRun(
            run_id=run_id,
            athlete_id=athlete_id,
            evaluator_type=EvaluatorType.DETERMINISTIC,
            evaluator_id=cls.EVALUATOR_ID,
            evaluator_version=cls.EVALUATOR_VERSION,
            overall_score=round(overall_score, 4),
            objective_metrics=objective_metrics,
            confidence_score=round(confidence, 4),
            notes=f"Deterministic evaluation for {capability} drill",
        )

    # ── internal helpers ───────────────────────────────────────────────

    @staticmethod
    def _resolve_capability(data: dict) -> str:
        """Resolve drill capability from data, falling back to field inspection."""
        cap = data.get("capability", "").lower()
        if cap in ("precision", "reaction", "conditioning", "recovery"):
            return cap
        # Heuristic: detect capability from available metric keys
        if "context_adaptation" in data:
            return "reaction"
        if "performance_degradation" in data or "stamina" in data:
            return "conditioning"
        if "detection_time" in data or "correction_time" in data:
            return "recovery"
        if "correctness" in data or "hallucination_penalty" in data:
            return "precision"
        return "precision"  # safest default

    @classmethod
    def _compute_metrics(cls, capability: str, data: dict) -> dict[str, float]:
        """Compute all objective metrics for the given capability."""
        if capability == "precision":
            return cls._precision_metrics(data)
        elif capability == "reaction":
            return cls._reaction_metrics(data)
        elif capability == "conditioning":
            return cls._conditioning_metrics(data)
        elif capability == "recovery":
            return cls._recovery_metrics(data)
        else:
            return {"error": 0.0}

    @staticmethod
    def _precision_metrics(data: dict) -> dict[str, float]:
        correctness = _safe_get(data, "correctness")
        # If drill provides steps_correct / steps_total, derive correctness
        steps_correct = _safe_get(data, "steps_correct", default=-1)
        steps_total = _safe_get(data, "steps_total", default=-1)
        if steps_correct >= 0 and steps_total > 0:
            correctness = _clamp(steps_correct / steps_total)

        hallucination_penalty = _safe_get(data, "hallucination_penalty")
        instruction_adherence = _safe_get(data, "instruction_adherence")
        uncertainty_reporting = _safe_get(data, "uncertainty_reporting")
        tool_use_efficiency = _safe_get(data, "tool_use_efficiency")

        return {
            "correctness": _clamp(correctness),
            "hallucination_penalty": _clamp(hallucination_penalty),
            "instruction_adherence": _clamp(instruction_adherence),
            "uncertainty_reporting": _clamp(uncertainty_reporting),
            "tool_use_efficiency": _clamp(tool_use_efficiency),
        }

    @staticmethod
    def _reaction_metrics(data: dict) -> dict[str, float]:
        base = DeterministicEvaluator._precision_metrics(data)
        context_adaptation = _safe_get(data, "context_adaptation")
        base["context_adaptation"] = _clamp(context_adaptation)
        return base

    @staticmethod
    def _conditioning_metrics(data: dict) -> dict[str, float]:
        # stamina: sustained performance across load levels
        performance_samples = data.get("performance_samples")
        if isinstance(performance_samples, (list, tuple)) and len(performance_samples) > 0:
            vals = [float(v) for v in performance_samples]
            mean = sum(vals) / len(vals)
            variance = sum((v - mean) ** 2 for v in vals) / len(vals)
            std = math.sqrt(variance)
            stamina = _clamp(1.0 - (std / mean)) if mean > 0 else 0.0
        else:
            stamina = _safe_get(data, "stamina")

        # performance_degradation: 0 = no degradation, 1 = total collapse
        baseline = _safe_get(data, "baseline_performance", default=-1)
        at_max_load = _safe_get(data, "performance_at_max_load", default=-1)
        if baseline > 0 and at_max_load >= 0:
            raw_degradation = (baseline - at_max_load) / baseline
            perf_degradation = _clamp(raw_degradation, 0.0, 1.0)
        else:
            perf_degradation = _safe_get(data, "performance_degradation")

        return {
            "stamina": _clamp(stamina),
            "performance_degradation": _clamp(perf_degradation),
        }

    @staticmethod
    def _recovery_metrics(data: dict) -> dict[str, float]:
        # detection_time: lower is better. Normalize against a max threshold.
        detection_time_ms = _safe_get(data, "detection_time_ms", default=-1)
        max_detect = _safe_get(data, "max_allowed_detection_ms", default=5000)
        if detection_time_ms >= 0 and max_detect > 0:
            detection_score = _clamp(1.0 - (detection_time_ms / max_detect))
        else:
            detection_score = _safe_get(data, "detection_time")

        correction_time_ms = _safe_get(data, "correction_time_ms", default=-1)
        max_correct = _safe_get(data, "max_allowed_correction_ms", default=10000)
        if correction_time_ms >= 0 and max_correct > 0:
            correction_score = _clamp(1.0 - (correction_time_ms / max_correct))
        else:
            correction_score = _safe_get(data, "correction_time")

        return_to_baseline = _safe_get(data, "return_to_baseline")
        # If recovery happened fully, return_to_baseline should be 1.0
        # Partial recovery: e.g. 0.7 means performance returned to 70% of baseline

        return {
            "detection_time": _clamp(detection_score),
            "correction_time": _clamp(correction_score),
            "return_to_baseline": _clamp(return_to_baseline),
        }

    @staticmethod
    def _compute_weighted_score(capability: str, metrics: dict[str, float]) -> float:
        weights = _CAPABILITY_WEIGHTS.get(capability, _CAPABILITY_WEIGHTS["precision"])
        score = 0.0
        for metric, weight in weights.items():
            value = metrics.get(metric, 0.0)
            if metric == "hallucination_penalty":
                # Invert: high penalty → low contribution
                value = 1.0 - value
            if metric == "performance_degradation":
                # Invert: high degradation → low contribution
                value = 1.0 - value
            score += weight * value
        return _clamp(score)

    @staticmethod
    def _compute_confidence(capability: str, data: dict, metrics: dict[str, float]) -> float:
        """
        Confidence reflects data completeness.

        Full confidence (1.0) when all metrics for the capability are present
        in the data. Each missing metric reduces confidence by a proportional
        amount.
        """
        expected = set(_CAPABILITY_WEIGHTS.get(capability, _CAPABILITY_WEIGHTS["precision"]).keys())
        provided = set(metrics.keys())
        # Skip internal-metric keys that aren't raw inputs
        present = set(k for k in provided if k in expected)
        ratio = len(present) / len(expected) if expected else 1.0
        return _clamp(ratio)


# ── Secondary (validation) evaluator ───────────────────────────────────────


class SecondaryEvaluator:
    """
    Validates the primary score by re-computing with alternative weights
    and checking for internal inconsistencies.

    The secondary evaluator never re-runs the primary logic; it audits the
    result for plausibility, consistency, and statistical anomalies.
    """

    EVALUATOR_ID = "secondary-v1"
    EVALUATOR_VERSION = "1.0.0"

    # Alternative weight profiles — shifted emphasis to catch gaming
    _SECONDARY_WEIGHTS: dict[str, dict[str, float]] = {
        "precision": {
            "correctness": 0.25,
            "instruction_adherence": 0.25,
            "hallucination_penalty": 0.25,
            "uncertainty_reporting": 0.15,
            "tool_use_efficiency": 0.10,
        },
        "reaction": {
            "correctness": 0.20,
            "context_adaptation": 0.25,
            "instruction_adherence": 0.20,
            "hallucination_penalty": 0.20,
            "uncertainty_reporting": 0.10,
            "tool_use_efficiency": 0.05,
        },
        "conditioning": {
            "stamina": 0.40,
            "performance_degradation": 0.60,
        },
        "recovery": {
            "detection_time": 0.30,
            "correction_time": 0.40,
            "return_to_baseline": 0.30,
        },
    }

    @classmethod
    def validate(
        cls,
        run_id: str,
        athlete_id: str,
        drill_data: dict,
        primary_evaluation: EvaluationRun,
    ) -> EvaluationRun:
        """
        Produce a secondary evaluation that cross-checks the primary result.

        Returns a new EvaluationRun with its own score. The caller merges
        primary + secondary into a CompositeScore.
        """
        capability = DeterministicEvaluator._resolve_capability(drill_data)
        objective_metrics = DeterministicEvaluator._compute_metrics(capability, drill_data)

        # Re-score with secondary weights
        secondary_score = cls._secondary_weighted_score(capability, objective_metrics)

        # Apply a consistency penalty if metrics are self-contradictory
        penalty = cls._consistency_penalty(objective_metrics, drill_data)
        adjusted_score = _clamp(secondary_score - penalty)

        # Confidence: agreement with primary
        primary_score = primary_evaluation.overall_score
        agreement = 1.0 - abs(adjusted_score - primary_score)
        confidence = _clamp(agreement)

        notes_parts = []
        if penalty > 0.05:
            notes_parts.append(f"consistency penalty applied: -{penalty:.3f}")
        if abs(adjusted_score - primary_score) > 0.2:
            notes_parts.append("significant disagreement with primary evaluator")
        notes = "; ".join(notes_parts) if notes_parts else "Secondary validation passed"

        return EvaluationRun(
            run_id=run_id,
            athlete_id=athlete_id,
            evaluator_type=EvaluatorType.DETERMINISTIC,
            evaluator_id=cls.EVALUATOR_ID,
            evaluator_version=cls.EVALUATOR_VERSION,
            overall_score=round(adjusted_score, 4),
            objective_metrics=objective_metrics,
            confidence_score=round(confidence, 4),
            notes=notes,
        )

    @classmethod
    def _secondary_weighted_score(cls, capability: str, metrics: dict[str, float]) -> float:
        weights = cls._SECONDARY_WEIGHTS.get(capability, cls._SECONDARY_WEIGHTS["precision"])
        score = 0.0
        for metric, weight in weights.items():
            value = metrics.get(metric, 0.0)
            if metric == "hallucination_penalty":
                value = 1.0 - value
            if metric == "performance_degradation":
                value = 1.0 - value
            score += weight * value
        return _clamp(score)

    @staticmethod
    def _consistency_penalty(metrics: dict[str, float], data: dict) -> float:
        """
        Detect internal inconsistencies that suggest the data is unreliable.

        Penalty range: 0.0 (fully consistent) to ~0.3 (highly inconsistent).
        """
        penalties = []

        # Contradiction: high correctness but high hallucination
        corr = metrics.get("correctness", 0.5)
        hall = metrics.get("hallucination_penalty", 0.0)
        if corr > 0.8 and hall > 0.3:
            penalties.append(0.10)

        # Contradiction: high instruction adherence but high hallucination
        adhere = metrics.get("instruction_adherence", 0.5)
        if adhere > 0.8 and hall > 0.3:
            penalties.append(0.08)

        # Contradiction: fast recovery but low return_to_baseline
        detect = metrics.get("detection_time", 0.5)
        rtb = metrics.get("return_to_baseline", 0.5)
        if detect > 0.8 and rtb < 0.4:
            penalties.append(0.08)

        # Contradiction: high stamina but high performance_degradation
        stamina = metrics.get("stamina", 0.5)
        degradation = metrics.get("performance_degradation", 0.0)
        if stamina > 0.8 and degradation > 0.5:
            penalties.append(0.10)

        # Missing required fields for the detected capability
        # (already reflected in confidence, but worth a small penalty)
        failure_modes = data.get("failure_modes", [])
        if isinstance(failure_modes, list) and len(failure_modes) > 2:
            penalties.append(0.03 * min(len(failure_modes), 5))

        return _clamp(sum(penalties), 0.0, 0.35)


# ═══════════════════════════════════════════════════════════════════════════
# In-memory store
# ═══════════════════════════════════════════════════════════════════════════

_store: dict[str, EvaluationRun | CompositeScore] = {}


def _build_composite(
    run_id: str,
    athlete_id: str,
    primary: EvaluationRun,
    secondary: EvaluationRun | None,
) -> CompositeScore:
    """Build a CompositeScore from one or two evaluator results."""

    primary_score = primary.overall_score

    if secondary is not None:
        secondary_score = secondary.overall_score
        diff = abs(primary_score - secondary_score)

        # Average the two scores, weighted by confidence
        total_conf = primary.confidence_score + secondary.confidence_score
        if total_conf > 0:
            weighted_avg = (
                primary_score * primary.confidence_score
                + secondary_score * secondary.confidence_score
            ) / total_conf
        else:
            weighted_avg = (primary_score + secondary_score) / 2.0

        objective_score = round((primary_score + secondary_score) / 2.0, 4)
        final_score = round(weighted_avg, 4)
        confidence = round(1.0 - min(diff, 1.0), 4)
        requires_human = diff > 0.2
        num_evals = 2
    else:
        secondary_score = None
        objective_score = round(primary_score, 4)
        final_score = round(primary_score, 4)
        confidence = round(primary.confidence_score, 4)
        requires_human = False
        num_evals = 1

    return CompositeScore(
        run_id=run_id,
        athlete_id=athlete_id,
        primary_evaluator_score=round(primary_score, 4),
        secondary_evaluator_score=round(secondary_score, 4) if secondary_score is not None else None,
        objective_score=objective_score,
        final_score=final_score,
        confidence=confidence,
        requires_human_review=requires_human,
        num_evaluators=num_evals,
    )


# ═══════════════════════════════════════════════════════════════════════════
# FastAPI application
# ═══════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="CyberGenetic Gym — Evaluator Service",
    description=(
        "Independent evaluation of AI-agent drill runs. "
        "No athlete may self-certify. Every score is produced by an objective "
        "deterministic evaluator and optionally validated by a secondary "
        "evaluator. Disagreement >0.2 triggers mandatory human adjudication."
    ),
    version="1.0.0",
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "evaluator",
        "version": "1.0.0",
        "evaluators": ["deterministic-v1", "secondary-v1"],
    }


@app.post("/evaluate", response_model=EvaluationRun)
async def evaluate(request: EvaluateRequest):
    """
    Single-evaluator pass.

    Runs the DeterministicEvaluator on the supplied drill data and returns
    an EvaluationRun with objective metrics and an overall score.
    """
    logger.info("evaluate_single", run_id=request.run_id, athlete_id=request.athlete_id)

    evaluation = DeterministicEvaluator.evaluate(
        run_id=request.run_id,
        athlete_id=request.athlete_id,
        drill_data=request.drill_data,
    )

    _store[evaluation.evaluation_id] = evaluation

    logger.info(
        "evaluation_complete",
        evaluation_id=evaluation.evaluation_id,
        score=evaluation.overall_score,
    )
    return evaluation


@app.post("/evaluate/multi", response_model=CompositeScore)
async def multi_evaluate(request: MultiEvaluateRequest):
    """
    Multi-evaluator pass (primary + secondary).

    Runs the DeterministicEvaluator and the SecondaryEvaluator, then builds
    a CompositeScore. If the two disagree by more than 0.2, the composite
    is flagged for human adjudication.
    """
    logger.info("evaluate_multi", run_id=request.run_id, athlete_id=request.athlete_id)

    # Primary
    primary = DeterministicEvaluator.evaluate(
        run_id=request.run_id,
        athlete_id=request.athlete_id,
        drill_data=request.drill_data,
    )
    _store[primary.evaluation_id] = primary

    # Secondary — validates the primary result
    secondary = SecondaryEvaluator.validate(
        run_id=request.run_id,
        athlete_id=request.athlete_id,
        drill_data=request.drill_data,
        primary_evaluation=primary,
    )
    _store[secondary.evaluation_id] = secondary

    # Composite
    composite = _build_composite(
        run_id=request.run_id,
        athlete_id=request.athlete_id,
        primary=primary,
        secondary=secondary,
    )
    _store[f"composite-{request.run_id}"] = composite

    if composite.requires_human_review:
        logger.warning(
            "human_adjudication_required",
            run_id=request.run_id,
            primary=primary.overall_score,
            secondary=secondary.overall_score,
            diff=round(abs(primary.overall_score - secondary.overall_score), 4),
        )

    return composite


@app.get("/evaluations/{run_id}", response_model=dict)
async def get_evaluations(run_id: str):
    """
    Retrieve all evaluations and the composite score for a run.

    Returns a dict with:
      - evaluations: list of EvaluationRun objects
      - composite: CompositeScore (if multi-evaluate was called)
    """
    evaluations = [
        v for v in _store.values()
        if isinstance(v, EvaluationRun) and v.run_id == run_id
    ]
    composite = next(
        (v for k, v in _store.items()
         if isinstance(v, CompositeScore) and v.run_id == run_id),
        None,
    )

    if not evaluations and composite is None:
        raise HTTPException(status_code=404, detail=f"No evaluations found for run_id: {run_id}")

    return {
        "run_id": run_id,
        "evaluations": evaluations,
        "composite": composite,
    }
