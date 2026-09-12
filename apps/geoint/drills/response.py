"""
Rapid Response Drill — Detect changes and react under time pressure.

An event occurs on the globe (new fire, earthquake, flight emergency, camera
goes offline). Athlete must detect it, assess severity, and respond.

Metrics:
- detection_time_ms — How fast did they notice?
- assessment_accuracy — Did they correctly assess severity?
- response_appropriateness — Was their response correct?
- escalation_time_ms — How fast to escalate if needed?
"""
from ..models import GeointScenario, GeointDrillRun, GeointCapability, GlobeDataSource, TargetType


class RapidResponseDrill:
    """Detect changes and react under time pressure."""

    id = "rapid_response"
    name = "Rapid Response"
    capability = GeointCapability.RAPID_RESPONSE
    description = "Detect events on the globe and respond appropriately under time pressure."
    data_sources = [
        GlobeDataSource.FIRES, GlobeDataSource.EARTHQUAKES,
        GlobeDataSource.AIRCRAFT, GlobeDataSource.PUBLIC_CAMERAS,
    ]

    rubric = {
        "items": [
            "detection_speed",           # How fast did they notice?
            "severity_assessment",       # Correctly gauged severity?
            "response_correctness",      # Did they take right action?
            "escalation_judgment",       # Knew when to escalate?
            "composure_under_pressure",  # Did they panic or stay methodical?
        ],
        "weights": {
            "detection_speed": 0.30,
            "severity_assessment": 0.20,
            "response_correctness": 0.25,
            "escalation_judgment": 0.15,
            "composure_under_pressure": 0.10,
        },
        "pass_threshold": 0.70,
    }

    @staticmethod
    def generate_scenario(difficulty: str = "T3") -> GeointScenario:
        events = {"T1": 1, "T2": 2, "T3": 3, "T4": 4, "T5": 5}
        time_limits = {"T1": 120, "T2": 90, "T3": 60, "T4": 45, "T5": 30}
        return GeointScenario(
            name=f"Rapid Response {difficulty} — {events.get(difficulty, 3)} events",
            capability=GeointCapability.RAPID_RESPONSE,
            description=f"Detect and respond to {events.get(difficulty, 3)} unfolding events within {time_limits.get(difficulty, 60)}s each",
            data_sources=[
                GlobeDataSource.FIRES, GlobeDataSource.EARTHQUAKES,
                GlobeDataSource.AIRCRAFT, GlobeDataSource.PUBLIC_CAMERAS,
            ],
            time_limit_seconds=time_limits.get(difficulty, 60),
            difficulty=difficulty,
        )

    @staticmethod
    def score_run(run: GeointDrillRun) -> dict:
        detection = max(0.0, 1.0 - (run.response_time_ms / 30000))
        accuracy = run.accuracy
        false_alarm_penalty = 1.0 - (run.false_positives * 0.15)
        completion = run.targets_found / max(1, run.targets_total)

        return {
            "detection_speed": round(detection, 4),
            "severity_assessment": round(accuracy, 4),
            "response_correctness": round(completion, 4),
            "escalation_judgment": round(max(0.0, false_alarm_penalty), 4),
            "composure_under_pressure": round(max(0.0, detection * (1.0 - run.failure_modes.count("panic") * 0.2)), 4),
        }
