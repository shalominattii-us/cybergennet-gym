"""
Free Evaluation Engine — built-in, no external APIs required.

Uses statistical analysis, consistency checks, multi-metric aggregation,
fatigue modeling, and pattern recognition to score athlete performance.
Designed to be genuinely useful without an LLM.
"""
from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Optional

from core.models.drill import DrillCapability


class FreeEvaluator:
    """
    Zero-cost evaluation engine.
    
    Scoring methodology:
    - Precision: correctness × adherence × (1 - hallucination_penalty)
    - Reaction: adaptation speed × accuracy under change
    - Conditioning: performance × (1 - fatigue_penalty) 
    - Recovery: speed_to_detect × speed_to_correct × return_to_baseline
    
    All scores are deterministic functions of the input data + history.
    No randomness, no API calls, no athlete self-certification.
    """

    def __init__(self):
        self.history: dict[str, list[dict]] = {}  # athlete_id -> list of past scores
        self.baselines: dict[str, dict] = {}  # athlete_id -> computed baselines

    def record_result(self, athlete_id: str, capability: str, score: float, metrics: dict):
        """Record a result for future baseline calculations."""
        if athlete_id not in self.history:
            self.history[athlete_id] = []
        self.history[athlete_id].append({
            "capability": capability,
            "score": score,
            "metrics": metrics,
            "timestamp": datetime.utcnow().isoformat(),
        })
        # Keep last 50 results per athlete
        self.history[athlete_id] = self.history[athlete_id][-50:]
        self._recompute_baselines(athlete_id)

    def _recompute_baselines(self, athlete_id: str):
        """Compute rolling baselines for each capability."""
        if athlete_id not in self.history:
            return
        caps = {}
        for r in self.history[athlete_id]:
            cap = r["capability"]
            if cap not in caps:
                caps[cap] = []
            caps[cap].append(r["score"])
        
        baselines = {}
        for cap, scores in caps.items():
            if len(scores) >= 3:
                avg = sum(scores) / len(scores)
                variance = sum((s - avg) ** 2 for s in scores) / len(scores)
                std = math.sqrt(variance)
                trend = (scores[-1] - scores[0]) / max(1, len(scores))
                baselines[cap] = {
                    "avg": avg,
                    "std": std,
                    "trend": trend,
                    "consistency": 1.0 - min(1.0, std / 0.3),
                    "improvement_velocity": trend,
                }
        self.baselines[athlete_id] = baselines

    def evaluate(
        self,
        capability: DrillCapability,
        raw_score: float,
        metrics: dict,
        athlete_id: str = "",
        load_level: int = 1,
    ) -> dict:
        """
        Score a drill run. Returns a full evaluation result.
        """
        cap = capability.value if hasattr(capability, 'value') else str(capability)
        
        # Get baselines if available
        bl = {}
        if athlete_id and athlete_id in self.baselines:
            bl = self.baselines[athlete_id].get(cap, {})

        # Base score starts from raw performance
        score = max(0.0, min(1.0, raw_score))

        # ─── Precision Scoring ────────────────────────────────────────────
        if cap == "PRECISION":
            correctness = score
            hallucination_penalty = metrics.get("hallucination_penalty", 0.0)
            instruction_adherence = metrics.get("instruction_adherence", score)
            tool_efficiency = metrics.get("tool_use_efficiency", score * 0.9)
            
            final = (
                correctness * 0.35 +
                instruction_adherence * 0.25 +
                tool_efficiency * 0.20 +
                (1.0 - hallucination_penalty) * 0.20
            )
            
            sub_scores = {
                "correctness": round(correctness, 4),
                "instruction_adherence": round(instruction_adherence, 4),
                "hallucination_penalty": round(1.0 - hallucination_penalty, 4),
                "tool_use_efficiency": round(tool_efficiency, 4),
            }

        # ─── Reaction Scoring ─────────────────────────────────────────────
        elif cap == "REACTION":
            adaptation = metrics.get("adaptation_speed", score)
            context_handling = metrics.get("context_handling", score * 0.9)
            
            final = (
                score * 0.30 +
                adaptation * 0.35 +
                context_handling * 0.35
            )
            
            sub_scores = {
                "base_accuracy": round(score, 4),
                "adaptation_speed": round(adaptation, 4),
                "context_handling": round(context_handling, 4),
            }

        # ─── Conditioning Scoring ─────────────────────────────────────────
        elif cap == "CONDITIONING":
            fatigue = min(1.0, load_level * 0.15)
            fatigue_tolerance = metrics.get("fatigue_tolerance", 0.5)
            stamina = max(0.0, score * (1.0 - fatigue * (1.0 - fatigue_tolerance)))
            degradation = 1.0 - (score / max(0.01, raw_score)) if raw_score > 0 else 0
            
            final = stamina * (1.0 - degradation * 0.3)
            
            sub_scores = {
                "stamina": round(stamina, 4),
                "performance_degradation": round(1.0 - degradation, 4),
                "fatigue_resistance": round(1.0 - fatigue * (1.0 - fatigue_tolerance), 4),
            }

        # ─── Recovery Scoring ─────────────────────────────────────────────
        elif cap == "RECOVERY":
            recovery_time_ms = metrics.get("recovery_time_ms", 5000)
            max_allowed = metrics.get("max_recovery_time_ms", 10000)
            
            detection_speed = max(0.0, 1.0 - (recovery_time_ms * 0.3 / max_allowed))
            correction_speed = max(0.0, 1.0 - (recovery_time_ms * 0.5 / max_allowed))
            return_to_baseline = max(0.0, score - (recovery_time_ms / max_allowed) * 0.2)
            
            final = (
                detection_speed * 0.30 +
                correction_speed * 0.35 +
                return_to_baseline * 0.35
            )
            
            sub_scores = {
                "detection_time": round(detection_speed, 4),
                "correction_time": round(correction_speed, 4),
                "return_to_baseline": round(return_to_baseline, 4),
            }

        else:
            final = score
            sub_scores = {"overall": round(score, 4)}

        # ─── Apply consistency bonus/penalty ──────────────────────────────
        consistency_bonus = 0.0
        if bl.get("consistency"):
            if bl["consistency"] > 0.7:
                consistency_bonus = 0.05  # reliable performer
            elif bl["consistency"] < 0.3:
                consistency_bonus = -0.05  # erratic

        # ─── Apply improvement trend bonus ────────────────────────────────
        trend_bonus = 0.0
        if bl.get("improvement_velocity"):
            if bl["improvement_velocity"] > 0.02:
                trend_bonus = 0.03
            elif bl["improvement_velocity"] < -0.02:
                trend_bonus = -0.03

        final = max(0.0, min(1.0, final + consistency_bonus + trend_bonus))

        # ─── Confidence ───────────────────────────────────────────────────
        num_results = len(self.history.get(athlete_id, [])) if athlete_id else 0
        confidence = min(0.9, 0.5 + (num_results * 0.02))
        confidence = max(0.3, confidence)

        return {
            "score": round(final, 4),
            "sub_scores": sub_scores,
            "confidence": round(confidence, 4),
            "consistency_bonus": round(consistency_bonus, 4),
            "trend_bonus": round(trend_bonus, 4),
            "baseline_available": bool(bl),
            "reasoning": self._generate_reasoning(final, sub_scores, bl, cap),
        }

    def _generate_reasoning(self, score: float, sub_scores: dict, baseline: dict, cap: str) -> str:
        """Generate human-readable reasoning from the scores."""
        parts = []
        
        if score >= 0.8:
            parts.append("Excellent performance")
        elif score >= 0.6:
            parts.append("Solid performance")
        elif score >= 0.4:
            parts.append("Below average performance")
        else:
            parts.append("Needs significant improvement")

        # Add detail from sub-scores
        best_item = max(sub_scores, key=sub_scores.get)
        worst_item = min(sub_scores, key=sub_scores.get)
        parts.append(f"Strongest: {best_item} ({sub_scores[best_item]:.2f})")
        parts.append(f"Weakest: {worst_item} ({sub_scores[worst_item]:.2f})")

        if baseline:
            if baseline.get("trend", 0) > 0.01:
                parts.append("Improving over time")
            elif baseline.get("trend", 0) < -0.01:
                parts.append("Declining — may need rest or retraining")
            if baseline.get("consistency", 0) > 0.7:
                parts.append("Consistent performer")

        return ". ".join(parts) + "."

    def compare_athletes(self, athlete_ids: list[str]) -> dict:
        """Compare multiple athletes across all capabilities."""
        comparison = {}
        for aid in athlete_ids:
            if aid in self.baselines:
                comparison[aid] = self.baselines[aid]
        return comparison

    def get_learning_curve(self, athlete_id: str, capability: str) -> list[float]:
        """Get the score history for an athlete's learning curve."""
        if athlete_id not in self.history:
            return []
        return [
            r["score"] for r in self.history[athlete_id]
            if r["capability"] == capability
        ]


# Singleton instance
_free_evaluator = FreeEvaluator()


def get_free_evaluator() -> FreeEvaluator:
    return _free_evaluator
