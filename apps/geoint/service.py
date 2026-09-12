"""
GEOINT Training Service — Globe-based intelligence drills.

Integrates God's Eye View globe data with CyberGenetic Gym's
credentialing, evaluation, and governance systems.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from core.events import emit_audit

from .models import (
    GeointCapability, GeointScenario, GeointDrillRun, GeointDrillRun,
    GlobeDataSource, GlobeCoordinate, GlobeBounds,
)
from .drills import DRILL_REGISTRY
from .judges.objective import ObjectiveJudge
from .judges.peer_review import PeerReviewPanel
from .judges.human import HumanAdjudicator
from .governance import GeointGovernanceGate, DATA_ACCESS_POLICY, CONSTITUTIONAL_RULES

app = FastAPI(title="GEOINT Training Service", version="0.1.0")

# ─── In-memory stores ──────────────────────────────────────────────────────
_scenarios: dict[str, GeointScenario] = {}
_runs: dict[str, GeointDrillRun] = {}
_judgments: dict[str, dict] = {}  # run_id -> judgment results


# ─── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "geoint-training",
        "scenarios": len(_scenarios),
        "runs_completed": len(_runs),
        "judges": ["objective", "peer_review", "human_adjudicator"],
        "governance": "sovereign-os-gated",
        "constitutional_rules": len(CONSTITUTIONAL_RULES),
    }


# ─── Scenarios ─────────────────────────────────────────────────────────────

@app.get("/scenarios")
async def list_scenarios(capability: Optional[str] = None):
    """List available training scenarios."""
    if capability:
        return [s for s in _scenarios.values() if s.capability.value == capability]
    return list(_scenarios.values())


@app.post("/scenarios", status_code=201)
async def create_scenario(capability: str, difficulty: str = "T3"):
    """Generate a scenario for the given capability and difficulty."""
    drill_cls = DRILL_REGISTRY.get(capability)
    if not drill_cls:
        raise HTTPException(400, f"Unknown capability: {capability}. Options: {list(DRILL_REGISTRY.keys())}")

    scenario = drill_cls.generate_scenario(difficulty)
    _scenarios[scenario.scenario_id] = scenario

    emit_audit(
        actor="system",
        subject=f"scenario:{scenario.scenario_id}",
        action="geoint.scenario.created",
        result="success",
        details=f"Capability: {capability}, Difficulty: {difficulty}",
    )

    return scenario


# ─── Drills ────────────────────────────────────────────────────────────────

@app.post("/drills/run", status_code=201)
async def run_drill(
    scenario_id: str,
    athlete_id: str,
    athlete_credential_level: int = Query(0),
):
    """Run a GEOINT drill. Checks governance gate first."""
    scenario = _scenarios.get(scenario_id)
    if not scenario:
        raise HTTPException(404, f"Scenario {scenario_id} not found")

    # Check governance gate for each data source
    for source in scenario.data_sources:
        access = GeointGovernanceGate.check_access(athlete_credential_level, source)
        if not access["allowed"]:
            raise HTTPException(403, f"Access denied: {access['reason']}")

    # Create the run
    run = GeointDrillRun(
        scenario_id=scenario_id,
        athlete_id=athlete_id,
        capability=scenario.capability,
    )
    _runs[run.run_id] = run

    emit_audit(
        actor=athlete_id,
        subject=f"run:{run.run_id}",
        action="geoint.drill.started",
        result="success",
        details=f"Scenario: {scenario.name}, Capability: {scenario.capability.value}",
    )

    return run


@app.post("/drills/{run_id}/complete")
async def complete_drill(
    run_id: str,
    targets_found: int = 0,
    targets_total: int = 0,
    completion_time_ms: int = 0,
    accuracy: float = 0.0,
    trajectory_error_m: float = 0.0,
    false_positives: int = 0,
    missed_targets: int = 0,
    response_time_ms: int = 0,
    fusion_accuracy: float = 0.0,
    coverage_pct: float = 0.0,
):
    """Submit drill results and trigger full evaluation pipeline."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")

    # Update run with results
    run.status = "COMPLETED"
    run.targets_found = targets_found
    run.targets_total = targets_total
    run.completion_time_ms = completion_time_ms
    run.accuracy = accuracy
    run.trajectory_error_m = trajectory_error_m
    run.false_positives = false_positives
    run.missed_targets = missed_targets
    run.response_time_ms = response_time_ms
    run.fusion_accuracy = fusion_accuracy
    run.coverage_pct = coverage_pct
    run.completed_at = datetime.utcnow()

    # ─── Run the full judgment pipeline ───────────────────────────────
    # Tier 1: Objective Judge (always)
    objective = ObjectiveJudge.evaluate(run)
    
    # Tier 2: Peer Review Panel
    peer = PeerReviewPanel.evaluate(run, objective["final_score"])
    
    # Tier 3: Check if human review needed
    review_check = HumanAdjudicator.requires_review(objective, peer)
    
    judgments = {
        "objective": objective,
        "peer_review": peer,
        "human_review_required": review_check["requires_review"],
        "human_review_reasons": review_check["reasons"],
        "final_score": peer["final_score"],  # Peer median is default final
        "composite_confidence": (objective["confidence"] + peer["confidence"]) / 2,
    }
    _judgments[run_id] = judgments

    emit_audit(
        actor="system",
        subject=f"run:{run_id}",
        action="geoint.drill.completed",
        result="success",
        details=f"Final score: {peer['final_score']:.4f}, Needs human: {review_check['requires_review']}",
    )

    return {
        "run_id": run_id,
        "status": "COMPLETED",
        "judgments": judgments,
    }


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get drill run results and judgments."""
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, f"Run {run_id} not found")
    return {
        "run": run,
        "judgments": _judgments.get(run_id),
    }


@app.get("/runs")
async def list_runs(athlete_id: Optional[str] = None):
    """List all drill runs."""
    if athlete_id:
        return [r for r in _runs.values() if r.athlete_id == athlete_id]
    return list(_runs.values())


# ─── Governance ────────────────────────────────────────────────────────────

@app.get("/governance/access")
async def check_data_access(athlete_level: int = Query(0)):
    """Check what data sources an athlete can access."""
    return {
        "athlete_level": athlete_level,
        "accessible_sources": GeointGovernanceGate.get_accessible_sources(athlete_level),
    }


@app.get("/governance/policy/{data_source}")
async def get_data_policy(data_source: str):
    """Get the access policy for a specific data source."""
    try:
        source = GlobeDataSource(data_source)
    except ValueError:
        raise HTTPException(400, f"Unknown data source: {data_source}")
    
    policy = DATA_ACCESS_POLICY.get(source)
    return {
        "data_source": data_source,
        "policy": policy,
        "constitutional_rules": CONSTITUTIONAL_RULES,
    }


@app.get("/governance/constitution")
async def get_constitution():
    """Get the immutable constitutional rules for GEOINT."""
    return {
        "constitutional_rules": CONSTITUTIONAL_RULES,
        "data_sources": {
            k.value: v for k, v in DATA_ACCESS_POLICY.items()
        },
    }


# ─── Judges info ───────────────────────────────────────────────────────────

@app.get("/judges")
async def list_judges():
    """List all judges and their evaluation criteria."""
    return {
        "judges": [
            {
                "id": "objective-judge",
                "name": "Objective Evaluator",
                "tier": 1,
                "type": "deterministic",
                "confidence": 0.95,
                "always_runs": True,
                "description": "Measures what can be measured — targets found, time, accuracy. No opinion, just facts.",
            },
            {
                "id": "peer-review-panel",
                "name": "Peer Review Panel",
                "tier": 2,
                "type": "multi-evaluator (3 judges)",
                "confidence": "0.70-0.95",
                "always_runs": True,
                "description": "Three independent evaluators with slightly different weight profiles. Median score used. Flags human review if disagreement > 0.15.",
            },
            {
                "id": "human-adjudicator",
                "name": "Human Adjudicator",
                "tier": 3,
                "type": "human override",
                "confidence": 1.0,
                "always_runs": False,
                "triggers": ["peer_disagreement", "athlete_appeal", "novel_scenario", "sovereign_policy", "credential_threshold"],
                "description": "Final authority. Can uphold, overturn, flag for retraining, or adjust credentials.",
            },
        ],
        "principle": "No athlete self-certifies. No single judge is the source of truth.",
    }
