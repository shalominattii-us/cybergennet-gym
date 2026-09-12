"""
Peer Review Panel — Multi-evaluator cross-validation.

Three independent evaluators each score the same drill run.
If they disagree by more than 0.15, the result is flagged for human review.
The panel score is the median, not the mean (robust against outliers).

Tier 2 — runs after Objective Judge.
"""
import statistics
from typing import Optional

from ..models import GeointDrillRun, GeointCapability
from ..drills import DRILL_REGISTRY


class PeerReviewPanel:
    """
    Tier 2 Judge — Cross-validation by multiple evaluators.
    
    Three independent judges score the run.
    Median score is used (rejects outliers).
    Disagreement > 0.15 → flag for human adjudication.
    """

    id = "peer-review-panel"
    name = "Peer Review Panel"
    tier = 2
    version = "1.0.0"
    NUM_EVALUATORS = 3
    DISAGREEMENT_THRESHOLD = 0.15

    @staticmethod
    def evaluate(run: GeointDrillRun, objective_score: float = 0.0) -> dict:
        """
        Run peer review with N independent evaluators.
        
        Each evaluator has a slightly different weight profile
        (simulating different perspectives).
        """
        drill_cls = DRILL_REGISTRY.get(
            run.capability.value if hasattr(run.capability, 'value') else run.capability
        )
        if not drill_cls:
            return {"error": f"No drill registered for {run.capability}"}

        rubric = drill_cls.rubric
        weight_variations = [
            _vary_weights(rubric["weights"], seed=1),
            _vary_weights(rubric["weights"], seed=2),
            _vary_weights(rubric["weights"], seed=3),
        ]

        base_scores = drill_cls.score_run(run)
        evaluator_scores = []

        for i, weights in enumerate(weight_variations):
            score = sum(
                base_scores.get(item, 0.0) * weights.get(item, 0.0)
                for item in rubric["items"]
            )
            evaluator_scores.append({
                "evaluator": f"peer-judge-{i + 1}",
                "score": round(score, 4),
                "weights": weights,
            })

        scores = [e["score"] for e in evaluator_scores]
        median_score = statistics.median(scores)
        score_range = max(scores) - min(scores)
        requires_human = score_range > PeerReviewPanel.DISAGREEMENT_THRESHOLD

        return {
            "judge_id": PeerReviewPanel.id,
            "judge_name": PeerReviewPanel.name,
            "tier": PeerReviewPanel.tier,
            "final_score": round(median_score, 4),
            "evaluators": evaluator_scores,
            "score_range": round(score_range, 4),
            "requires_human_adjudication": requires_human,
            "disagreement_triggered": score_range > 0.2,
            "confidence": round(0.7 + (1.0 - score_range) * 0.25, 4),
            "verdict": "PASS" if median_score >= rubric["pass_threshold"] else "FAIL",
            "reasoning": _generate_peer_reasoning(evaluator_scores, median_score, requires_human),
        }


def _vary_weights(base_weights: dict, seed: int) -> dict:
    """Slightly shift weights to simulate different evaluator perspectives."""
    import random
    rng = random.Random(seed)
    varied = {}
    for k, v in base_weights.items():
        shift = rng.uniform(-0.03, 0.03)
        varied[k] = max(0.05, v + shift)
    # Normalize
    total = sum(varied.values())
    return {k: v / total for k, v in varied.items()}


def _generate_peer_reasoning(evaluators: list, median: float, needs_human: bool) -> str:
    scores = [e["score"] for e in evaluators]
    parts = [f"Peer review: {len(evaluators)} evaluators"]
    parts.append(f"Scores: {', '.join(f'{s:.4f}' for s in scores)}")
    parts.append(f"Median: {median:.4f}")

    if needs_human:
        parts.append("⚠️ Flagged for human adjudication — evaluators disagree")

    return ". ".join(parts) + "."
