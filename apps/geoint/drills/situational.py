"""
Situational Awareness Drill — Maintain multi-target awareness simultaneously.

Athlete is presented with 5-15 simultaneous events (flights, ships, fires,
earthquakes) and must track all of them, detecting changes and correlations.

Metrics:
- coverage_pct — % of events detected
- accuracy — correct classification of each event
- response_time_ms — time to notice a change (e.g. flight diverts)
- missed_targets — events never noticed
- false_positives — non-existent events reported
"""
from ..models import GeointScenario, GeointDrillRun, GeointCapability, GlobeDataSource, TargetType


class SituationalAwarenessDrill:
    """Maintain awareness of multiple simultaneous globe events."""

    id = "situational_awareness"
    name = "Situational Awareness"
    capability = GeointCapability.SITUATIONAL_AWARENESS
    description = "Track multiple simultaneous events and detect changes in real time."
    data_sources = [
        GlobeDataSource.AIRCRAFT, GlobeDataSource.SHIPS,
        GlobeDataSource.FIRES, GlobeDataSource.EARTHQUAKES,
    ]

    rubric = {
        "items": [
            "coverage_completeness",     # % of events detected
            "classification_accuracy",   # Correctly identified event types
            "change_detection",          # Noticed when something changed
            "prioritization",            # Correctly prioritized critical events
            "sustained_attention",       # Maintained track over duration
        ],
        "weights": {
            "coverage_completeness": 0.30,
            "classification_accuracy": 0.20,
            "change_detection": 0.25,
            "prioritization": 0.15,
            "sustained_attention": 0.10,
        },
        "pass_threshold": 0.65,
    }

    @staticmethod
    def generate_scenario(difficulty: str = "T3") -> GeointScenario:
        event_counts = {"T1": 5, "T2": 8, "T3": 10, "T4": 12, "T5": 15}
        changes = {"T1": 1, "T2": 2, "T3": 3, "T4": 4, "T5": 6}
        return GeointScenario(
            name=f"Situational Awareness {difficulty} — {event_counts.get(difficulty, 10)} events",
            capability=GeointCapability.SITUATIONAL_AWARENESS,
            description=f"Track {event_counts.get(difficulty, 10)} simultaneous events with {changes.get(difficulty, 3)} changes",
            data_sources=[
                GlobeDataSource.AIRCRAFT, GlobeDataSource.SHIPS,
                GlobeDataSource.FIRES, GlobeDataSource.EARTHQUAKES,
            ],
            targets=[{"type": "event", "count": event_counts.get(difficulty, 10)}],
            time_limit_seconds=600,
            difficulty=difficulty,
        )

    @staticmethod
    def score_run(run: GeointDrillRun) -> dict:
        coverage = run.coverage_pct / 100.0
        miss_rate = run.missed_targets / max(1, run.missed_targets + run.targets_found)
        change_speed = max(0.0, 1.0 - (run.response_time_ms / 60000))
        accuracy = run.accuracy

        return {
            "coverage_completeness": round(coverage, 4),
            "classification_accuracy": round(accuracy, 4),
            "change_detection": round(change_speed, 4),
            "prioritization": round((1.0 - miss_rate) * coverage, 4),
            "sustained_attention": round(max(0.0, 1.0 - (run.false_positives * 0.1)), 4),
        }
