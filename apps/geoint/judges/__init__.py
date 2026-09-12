"""
GEOINT Judge System — Who judges, how, and by what standards.

Three tiers of judgment:
1. Objective Evaluator (deterministic — always runs first)
2. Peer Review Panel (cross-validation by multiple evaluators)
3. Human Adjudicator (override authority for edge cases)

No athlete self-certifies. No single judge is the source of truth.
"""
from .objective import ObjectiveJudge
from .peer_review import PeerReviewPanel
from .human import HumanAdjudicator

JUDGE_REGISTRY = {
    "objective": ObjectiveJudge,
    "peer_review": PeerReviewPanel,
    "human": HumanAdjudicator,
}
