"""
Human Adjudicator — Final authority for edge cases.

Only called when:
1. Peer review panel disagrees (>0.15 range)
2. Athlete appeals the objective verdict
3. The scenario involves a novel situation with no precedent
4. SovereignOS policy requires human approval

The human adjudicator can:
- Uphold the objective/peer verdict
- Overturn with written reasoning
- Flag the scenario for retraining
- Recommend credential adjustment
"""
from datetime import datetime
from typing import Optional

from ..models import GeointDrillRun


class HumanAdjudicator:
    """
    Tier 3 Judge — Human override authority.
    
    The final check in the system. No automation above this.
    Every human decision is logged, audited, and fed back into the rubric.
    """

    id = "human-adjudicator"
    name = "Human Adjudicator"
    tier = 3
    version = "1.0.0"

    # Grounds for human review
    REVIEW_TRIGGERS = [
        "peer_disagreement",       # Peer panel couldn't agree
        "athlete_appeal",          # Athlete contested the result
        "novel_scenario",          # No precedent for this situation
        "sovereign_policy",        # SovereignOS requires human sign-off
        "credential_threshold",    # Crosses a credential boundary
    ]

    @staticmethod
    def requires_review(objective: dict, peer: dict, athlete_level: int = 0) -> dict:
        """Determine if human review is needed."""
        reasons = []

        if peer.get("requires_human_adjudication"):
            reasons.append("peer_disagreement")

        if objective.get("passed") is False and athlete_level >= 4:
            reasons.append("credential_threshold")

        if peer.get("disagreement_triggered"):
            reasons.append("peer_disagreement")

        return {
            "requires_review": len(reasons) > 0,
            "reasons": reasons,
            "recommended_action": _recommend_action(reasons, objective, peer),
        }

    @staticmethod
    def adjudicate(
        run: GeointDrillRun,
        objective_verdict: dict,
        peer_verdict: dict,
        human_decision: str,  # "uphold", "overturn", "flag_retrain", "adjust_credential"
        human_reasoning: str,
        new_score: Optional[float] = None,
    ) -> dict:
        """
        Record a human adjudication decision.
        
        This is the final word. Cannot be appealed.
        """
        return {
            "judge_id": HumanAdjudicator.id,
            "judge_name": HumanAdjudicator.name,
            "tier": HumanAdjudicator.tier,
            "decision": human_decision,
            "original_objective_score": objective_verdict.get("final_score"),
            "original_peer_score": peer_verdict.get("final_score"),
            "final_score": new_score if new_score is not None else peer_verdict.get("final_score", objective_verdict.get("final_score")),
            "human_reasoning": human_reasoning,
            "adjudicated_at": datetime.utcnow().isoformat(),
            "precedent_set": human_decision == "overturn",  # Overturns set precedent
            "confidence": 1.0,  # Human is final
            "verdict": "PASS" if (new_score or peer_verdict.get("final_score", 0)) >= 0.7 else "FAIL",
        }


def _recommend_action(reasons: list, objective: dict, peer: dict) -> str:
    if "peer_disagreement" in reasons:
        return "human_review_required"
    if "credential_threshold" in reasons:
        return "credential_review"
    return "standard_review"
