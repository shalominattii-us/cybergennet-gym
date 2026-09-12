"""
Reconnaissance Drill — Find and track specific targets on the globe.

Athlete is given a target description (e.g. "Boeing 787 over Atlantic at FL380")
and must locate it, lock on, and maintain track.

Metrics:
- targets_found / targets_total (recall)
- accuracy (precision — false positives penalized)
- completion_time_ms (speed)
- trajectory_error_m (tracking quality)
- coverage_pct (search efficiency)
"""
from datetime import datetime
from typing import Optional

from ..models import GeointScenario, GeointDrillRun, GeointCapability, GlobeDataSource, TargetType


class ReconnaissanceDrill:
    """Target reconnaissance — find and track."""

    id = "reconnaissance"
    name = "Target Reconnaissance"
    capability = GeointCapability.RECONNAISSANCE
    description = "Locate specific targets on the globe and maintain tracking lock."
    data_sources = [GlobeDataSource.AIRCRAFT, GlobeDataSource.SHIPS]

    rubric = {
        "items": [
            "target_acquisition",       # Did they find the right target?
            "tracking_maintenance",     # Did they hold lock?
            "identification_accuracy",  # Did they correctly identify it?
            "search_efficiency",        # How efficiently did they search?
            "reporting_quality",        # How complete was their report?
        ],
        "weights": {
            "target_acquisition": 0.35,
            "tracking_maintenance": 0.25,
            "identification_accuracy": 0.20,
            "search_efficiency": 0.10,
            "reporting_quality": 0.10,
        },
        "pass_threshold": 0.70,
        "time_bonus_threshold_ms": 120000,  # Bonus if completed within 2 min
    }

    @staticmethod
    def generate_scenario(difficulty: str = "T3") -> GeointScenario:
        targets_count = {"T1": 1, "T2": 2, "T3": 3, "T4": 5, "T5": 8}
        time_limits = {"T1": 600, "T2": 450, "T3": 300, "T4": 200, "T5": 120}
        return GeointScenario(
            name=f"Recon {difficulty} — Find {targets_count.get(difficulty, 3)} targets",
            capability=GeointCapability.RECONNAISSANCE,
            description=f"Locate and track {targets_count.get(difficulty, 3)} targets within {time_limits.get(difficulty, 300)}s",
            data_sources=[GlobeDataSource.AIRCRAFT, GlobeDataSource.SHIPS, GlobeDataSource.SATELLITES],
            targets=[{"type": t, "count": targets_count.get(difficulty, 3)} for t in [TargetType.AIRCRAFT]],
            time_limit_seconds=time_limits.get(difficulty, 300),
            difficulty=difficulty,
        )

    @staticmethod
    def score_run(run: GeointDrillRun) -> dict:
        """Score a recon run against the rubric."""
        recall = run.targets_found / max(1, run.targets_total)
        precision = run.targets_found / max(1, run.targets_found + run.false_positives)
        f1 = 2 * (precision * recall) / max(0.001, precision + recall)

        time_score = max(0.0, 1.0 - (run.completion_time_ms / 300000))
        track_score = max(0.0, 1.0 - (run.trajectory_error_m / 10000))
        coverage = run.coverage_pct / 100.0

        return {
            "target_acquisition": round(recall, 4),
            "tracking_maintenance": round(track_score, 4),
            "identification_accuracy": round(f1, 4),
            "search_efficiency": round(coverage, 4),
            "reporting_quality": round((recall + precision) / 2, 4),
        }
