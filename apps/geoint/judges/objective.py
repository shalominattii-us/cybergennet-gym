"""
Objective Judge — Deterministic, first-pass evaluator.

Always runs. Never varies. Measures what can be measured:
- Did the athlete find the target? (boolean)
- How fast? (time)
- How accurate? (position error)
- How complete? (coverage)

This judge has NO opinion on quality, creativity, or style.
It reports facts. The rubric applies weights.
"""
import math
from typing import Optional

from ..models import GeointDrillRun, GeointCapability
from ..drills import DRILL_REGISTRY


class ObjectiveJudge:
    """
    Tier 1 Judge — Deterministic.
    
    Verdict: numeric scores for each rubric item.
    Cannot be appealed. Provides the baseline for all higher judges.
    """

    id = "objective-judge"
    name = "Objective Evaluator"
    tier = 1
    version = "1.0.0"

    @staticmethod
    def evaluate(run: GeointDrillRun) -> dict:
        """Run deterministic scoring against the drill's rubric."""
        drill_cls = DRILL_REGISTRY.get(run.capability.value if hasattr(run.capability, 'value') else run.capability)
        if not drill_cls:
            return {"error": f"No drill registered for {run.capability}"}

        sub_scores = drill_cls.score_run(run)
        rubric = drill_cls.rubric

        # Compute weighted final score
        final = sum(
            sub_scores.get(item, 0.0) * rubric["weights"].get(item, 0.0)
            for item in rubric["items"]
        )

        # Determine pass/fail
        passed = final >= rubric["pass_threshold"]

        # Time bonus
        time_bonus = 0.0
        if "time_bonus_threshold_ms" in rubric:
            if run.completion_time_ms <= rubric["time_bonus_threshold_ms"]:
                time_bonus = 0.05

        return {
            "judge_id": ObjectiveJudge.id,
            "judge_name": ObjectiveJudge.name,
            "tier": ObjectiveJudge.tier,
            "final_score": round(min(1.0, final + time_bonus), 4),
            "raw_score": round(final, 4),
            "time_bonus": round(time_bonus, 4),
            "passed": passed,
            "sub_scores": sub_scores,
            "confidence": 0.95,  # Deterministic = high confidence
            "verdict": "PASS" if passed else "FAIL",
            "reasoning": _generate_objective_reasoning(final, sub_scores, passed, run),
        }


def _generate_objective_reasoning(score: float, sub_scores: dict, passed: bool, run: GeointDrillRun) -> str:
    """Generate deterministic reasoning."""
    parts = [f"Objective evaluation for {run.capability.value if hasattr(run.capability, 'value') else run.capability} drill"]
    parts.append(f"Overall score: {score:.4f} ({'PASS' if passed else 'FAIL'})")

    best = max(sub_scores, key=sub_scores.get)
    worst = min(sub_scores, key=sub_scores.get)
    parts.append(f"Strongest metric: {best} ({sub_scores[best]:.4f})")
    parts.append(f"Weakest metric: {worst} ({sub_scores[worst]:.4f})")

    if run.targets_total > 0:
        pct = (run.targets_found / run.targets_total) * 100
        parts.append(f"Targets: {run.targets_found}/{run.targets_total} ({pct:.0f}%)")

    if run.completion_time_ms > 0:
        parts.append(f"Completion time: {run.completion_time_ms / 1000:.1f}s")

    if run.false_positives > 0:
        parts.append(f"False positives: {run.false_positives}")

    return ". ".join(parts) + "."
