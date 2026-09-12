"""
Data Fusion Drill — Cross-reference multiple data sources.

Athlete is given a scenario that requires combining data from multiple sources:
flight tracks + camera feeds, ship positions + weather, fire + satellite imagery.
They must produce a coherent intelligence picture.

Metrics:
- cross_references_made — Number of source connections identified
- fusion_accuracy — Correctness of cross-referenced conclusions
- source_confidence — Did they correctly assess source reliability?
- completeness — Did they identify all relevant connections?
- reporting_clarity — Quality of the fused intelligence report
"""
from ..models import GeointScenario, GeointDrillRun, GeointCapability, GlobeDataSource, TargetType


class DataFusionDrill:
    """Cross-reference multiple data sources into intelligence."""

    id = "data_fusion"
    name = "Data Fusion"
    capability = GeointCapability.DATA_FUSION
    description = "Cross-reference multiple globe data sources into a coherent intelligence picture."
    data_sources = [
        GlobeDataSource.AIRCRAFT, GlobeDataSource.SHIPS,
        GlobeDataSource.PUBLIC_CAMERAS, GlobeDataSource.FIRES,
        GlobeDataSource.EARTHQUAKES, GlobeDataSource.WEATHER,
    ]

    rubric = {
        "items": [
            "cross_referencing",         # Connected data across sources?
            "fusion_accuracy",           # Correct conclusions from fused data?
            "source_criticism",          # Correctly assessed reliability?
            "intelligence_completeness",  # All relevant connections found?
            "report_quality",            # Clear, structured intelligence product?
        ],
        "weights": {
            "cross_referencing": 0.25,
            "fusion_accuracy": 0.30,
            "source_criticism": 0.15,
            "intelligence_completeness": 0.15,
            "report_quality": 0.15,
        },
        "pass_threshold": 0.70,
    }

    @staticmethod
    def generate_scenario(difficulty: str = "T3") -> GeointScenario:
        sources_count = {"T1": 2, "T2": 3, "T3": 4, "T4": 5, "T5": 6}
        time_limits = {"T1": 600, "T2": 500, "T3": 400, "T4": 300, "T5": 200}
        return GeointScenario(
            name=f"Data Fusion {difficulty} — {sources_count.get(difficulty, 4)} sources",
            capability=GeointCapability.DATA_FUSION,
            description=f"Cross-reference {sources_count.get(difficulty, 4)} data sources into intelligence",
            data_sources=[
                GlobeDataSource.AIRCRAFT, GlobeDataSource.SHIPS,
                GlobeDataSource.PUBLIC_CAMERAS, GlobeDataSource.FIRES,
            ][:sources_count.get(difficulty, 4)],
            time_limit_seconds=time_limits.get(difficulty, 400),
            difficulty=difficulty,
        )

    @staticmethod
    def score_run(run: GeointDrillRun) -> dict:
        accuracy = run.fusion_accuracy
        coverage = run.targets_found / max(1, run.targets_total)
        speed = max(0.0, 1.0 - (run.completion_time_ms / 600000))
        false_alarm_rate = run.false_positives / max(1, run.false_positives + run.targets_found)

        return {
            "cross_referencing": round(coverage, 4),
            "fusion_accuracy": round(accuracy, 4),
            "source_criticism": round(max(0.0, 1.0 - false_alarm_rate), 4),
            "intelligence_completeness": round(coverage * accuracy, 4),
            "report_quality": round((accuracy + coverage + speed) / 3, 4),
        }
