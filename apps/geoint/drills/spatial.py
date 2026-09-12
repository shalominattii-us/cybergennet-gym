"""
Spatial Reasoning Drill — Navigate the globe and predict trajectories.

Athlete must navigate to coordinates, predict where a moving target will be,
calculate intercept courses, and understand spatial relationships.

Metrics:
- navigation_accuracy — Did they reach the right location?
- trajectory_prediction_error_m — How wrong was their prediction?
- intercept_calculation — Did they find the right intercept point?
- spatial_awareness — Understanding of geographic relationships
- efficiency — Did they take an optimal path?
"""
from ..models import GeointScenario, GeointDrillRun, GeointCapability, GlobeDataSource, TargetType


class SpatialReasoningDrill:
    """Navigate the globe and predict trajectories."""

    id = "spatial_reasoning"
    name = "Spatial Reasoning"
    capability = GeointCapability.SPATIAL_REASONING
    description = "Navigate the globe, predict trajectories, and calculate intercepts."
    data_sources = [
        GlobeDataSource.AIRCRAFT, GlobeDataSource.SHIPS,
        GlobeDataSource.SATELLITES,
    ]

    rubric = {
        "items": [
            "navigation_accuracy",            # Reached correct location?
            "trajectory_prediction",           # Predicted future position correctly?
            "intercept_calculation",           # Calculated intercept course?
            "geographic_reasoning",            # Understood spatial relationships?
            "route_efficiency",                # Took optimal path?
        ],
        "weights": {
            "navigation_accuracy": 0.25,
            "trajectory_prediction": 0.30,
            "intercept_calculation": 0.20,
            "geographic_reasoning": 0.15,
            "route_efficiency": 0.10,
        },
        "pass_threshold": 0.65,
    }

    @staticmethod
    def generate_scenario(difficulty: str = "T3") -> GeointScenario:
        nav_points = {"T1": 1, "T2": 2, "T3": 3, "T4": 5, "T5": 8}
        time_limits = {"T1": 300, "T2": 240, "T3": 180, "T4": 120, "T5": 90}
        return GeointScenario(
            name=f"Spatial Reasoning {difficulty} — {nav_points.get(difficulty, 3)} navigations",
            capability=GeointCapability.SPATIAL_REASONING,
            description=f"Navigate to {nav_points.get(difficulty, 3)} points, predict {nav_points.get(difficulty, 3) // 2} trajectories",
            data_sources=[GlobeDataSource.AIRCRAFT, GlobeDataSource.SATELLITES],
            time_limit_seconds=time_limits.get(difficulty, 180),
            difficulty=difficulty,
        )

    @staticmethod
    def score_run(run: GeointDrillRun) -> dict:
        nav_accuracy = max(0.0, 1.0 - (run.trajectory_error_m / 50000))
        completion = run.targets_found / max(1, run.targets_total)
        speed = max(0.0, 1.0 - (run.completion_time_ms / 300000))
        coverage = run.coverage_pct / 100.0

        return {
            "navigation_accuracy": round(nav_accuracy, 4),
            "trajectory_prediction": round(max(0.0, 1.0 - (run.trajectory_error_m / 100000)), 4),
            "intercept_calculation": round(completion * nav_accuracy, 4),
            "geographic_reasoning": round(coverage, 4),
            "route_efficiency": round(speed * coverage, 4),
        }
