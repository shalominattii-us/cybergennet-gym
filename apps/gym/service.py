"""
CyberGenetic Gym — Athlete management, training programs, and drill execution service.

This is the MVP FastAPI service using in-memory storage. It manages athletes,
training programs, drills, and performance tracking with audit-event emission
on all state changes.
"""

from __future__ import annotations

import logging
import random
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

from core.models.athlete import (
    Athlete,
    AthleteCreate,
    AthleteDivision,
    AthleteStatus,
    TraitManifest,
)
from core.models.drill import (
    DrillCapability,
    DrillDefinition,
    DrillDifficulty,
    DrillRun,
    DrillRunMetrics,
    DrillStatus,
    GymProgram,
)
from core.events import emit_audit

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("cybergennet.gym")

# ---------------------------------------------------------------------------
# In-memory stores (MVP — no DB dependency yet)
# ---------------------------------------------------------------------------

_athletes: dict[str, Athlete] = {}
_drills: dict[str, DrillDefinition] = {}
_drill_runs: dict[str, DrillRun] = {}
_programs: dict[str, GymProgram] = {}
_performance_log: dict[str, list[dict]] = {}  # athlete_id -> list of {metric, value, timestamp}
_athlete_loads: dict[str, float] = {}  # athlete_id -> current load_level (0.0 - 1.0)

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

def _seed_data() -> None:
    """Create the initial CORE athlete RECON-01 with default traits."""
    if "RECON-01" in {a.name for a in _athletes.values()}:
        return

    recon = Athlete(
        name="RECON-01",
        division=AthleteDivision.CORE,
        tier="T1",
        status=AthleteStatus.REGISTERED,
    )
    # Override default trait values for the seeded athlete
    recon.trait_manifest.precision = 0.72
    recon.trait_manifest.coordination = 0.68
    recon.trait_manifest.fatigue_tolerance = 0.81
    recon.trait_manifest.recovery = 0.65
    recon.trait_manifest.learning_rate = 0.70
    recon.trait_manifest.caution = 0.55
    recon.trait_manifest.creativity = 0.40
    recon.trait_manifest.tool_affinity = 0.60
    recon.created_at = datetime.now(timezone.utc)
    recon.updated_at = datetime.now(timezone.utc)

    _athletes[recon.athlete_id] = recon
    _performance_log[recon.athlete_id] = []
    _athlete_loads[recon.athlete_id] = 0.0

    emit_audit(
        actor="system",
        subject=f"athlete:{recon.athlete_id}",
        action="athlete.seeded",
        result="success",
        details=f'{{"name": "{recon.name}", "division": "{recon.division}"}}',
    )
    logger.info("Seeded CORE athlete %s (%s)", recon.name, recon.athlete_id)


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------

def _compute_drill_score(
    capability: DrillCapability,
    traits: TraitManifest,
    load_level: float,
    difficulty: DrillDifficulty,
) -> DrillRunMetrics:
    """Simulate drill execution and produce scoring metrics.

    Scoring formulas (MVP):
      - PRECISION   : 0.60 – 1.00  influenced by ``trait_manifest.precision``
      - REACTION    : 0.50 – 0.95  influenced by ``trait_manifest.coordination``
      - CONDITIONING: degrades as ``load_level`` rises; driven by fatigue_tolerance
      - RECOVERY    : 0.40 – 0.90  influenced by recovery; recovery_time_ms inverse
      - INTEGRATION : blended composite of the four primary traits
    """
    difficulty_mod = {
        DrillDifficulty.BASIC: 1.0,
        DrillDifficulty.INTERMEDIATE: 0.9,
        DrillDifficulty.ADVANCED: 0.75,
        DrillDifficulty.ELITE: 0.55,
    }[difficulty]

    noise = random.uniform(-0.05, 0.05)

    if capability == DrillCapability.PRECISION:
        raw = 0.60 + (traits.precision * 0.40) + noise
        raw = max(0.0, min(1.0, raw))
        adjusted = raw * difficulty_mod
        return DrillRunMetrics(
            raw_score=round(raw, 4),
            adjusted_score=round(adjusted, 4),
            load_impact=round(0.15 + traits.precision * 0.10, 4),
            fatigue_factor=round(load_level * 0.2, 4),
        )

    elif capability == DrillCapability.REACTION:
        raw = 0.50 + (traits.coordination * 0.45) + noise
        raw = max(0.0, min(1.0, raw))
        adjusted = raw * difficulty_mod
        return DrillRunMetrics(
            raw_score=round(raw, 4),
            adjusted_score=round(adjusted, 4),
            recovery_time_ms=round(800.0 + (1.0 - traits.coordination) * 600.0, 2),
            load_impact=round(0.10 + traits.coordination * 0.08, 4),
            fatigue_factor=round(load_level * 0.15, 4),
        )

    elif capability == DrillCapability.CONDITIONING:
        load_penalty = load_level * (1.0 - traits.fatigue_tolerance)
        raw = max(0.0, traits.fatigue_tolerance - load_penalty + noise)
        raw = min(1.0, raw)
        adjusted = raw * difficulty_mod
        return DrillRunMetrics(
            raw_score=round(raw, 4),
            adjusted_score=round(adjusted, 4),
            recovery_time_ms=round(1500.0 + (1.0 - traits.fatigue_tolerance) * 2000.0, 2),
            load_impact=round(0.25 + load_level * 0.30, 4),
            fatigue_factor=round(load_level * 0.40, 4),
        )

    elif capability == DrillCapability.RECOVERY:
        raw = 0.40 + (traits.recovery * 0.50) + noise
        raw = max(0.0, min(1.0, raw))
        adjusted = raw * difficulty_mod
        recovery_time = 1000.0 + (1.0 - traits.recovery) * 4000.0
        return DrillRunMetrics(
            raw_score=round(raw, 4),
            adjusted_score=round(adjusted, 4),
            recovery_time_ms=round(recovery_time, 2),
            load_impact=round(0.05 + traits.recovery * 0.05, 4),
            fatigue_factor=round(load_level * 0.10, 4),
        )

    elif capability == DrillCapability.INTEGRATION:
        composite = (
            traits.precision * 0.25
            + traits.coordination * 0.25
            + traits.fatigue_tolerance * 0.25
            + traits.recovery * 0.25
        )
        raw = max(0.0, min(1.0, composite + noise))
        adjusted = raw * difficulty_mod
        return DrillRunMetrics(
            raw_score=round(raw, 4),
            adjusted_score=round(adjusted, 4),
            recovery_time_ms=round(1200.0 + (1.0 - composite) * 2500.0, 2),
            load_impact=round(0.20 + load_level * 0.20, 4),
            fatigue_factor=round(load_level * 0.25, 4),
        )

    return DrillRunMetrics(raw_score=0.0, adjusted_score=0.0)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class RegisterAthleteResponse(BaseModel):
    """Public athlete representation returned to API consumers."""
    athlete_id: str
    name: str
    division: str
    tier: str
    generation: int
    status: str
    credential_level: int
    trait_manifest: dict
    constitutional_genome: dict
    created_at: datetime
    updated_at: datetime
    last_training_at: Optional[datetime] = None


class ProgramCreate(BaseModel):
    """Request body for creating a training program."""
    name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    drill_ids: list[str] = Field(default_factory=list)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class DrillCreate(BaseModel):
    """Request body for creating a new drill definition."""
    name: str = Field(..., min_length=1, max_length=128)
    capability: str
    difficulty: str = "BASIC"
    description: str = ""


class PerformanceRecord(BaseModel):
    """A recorded performance metric entry."""
    metric: str
    value: float
    timestamp: str


class AthletePerformanceSummary(BaseModel):
    """Aggregate performance summary for an athlete."""
    athlete_id: str
    athlete_name: str
    total_runs: int
    completed_runs: int
    average_score: float
    best_score: float
    worst_score: float
    current_load: float
    current_tier: str
    division: str
    status: str
    trait_manifest: dict


class PerformanceHistory(BaseModel):
    """Performance history response."""
    athlete_id: str
    athlete_name: str
    records: list[PerformanceRecord]
    count: int


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    _seed_data()
    yield


app = FastAPI(
    title="CyberGenetic Gym",
    description="Athlete management, training programs, and drill execution service.",
    version="0.1.0",
    lifespan=lifespan,
)


# =========================== ATHLETE ENDPOINTS ============================


def _to_athlete_response(a: Athlete) -> RegisterAthleteResponse:
    return RegisterAthleteResponse(
        athlete_id=a.athlete_id,
        name=a.name,
        division=a.division if isinstance(a.division, str) else a.division.value,
        tier=a.tier,
        generation=a.generation,
        status=a.status if isinstance(a.status, str) else a.status.value,
        credential_level=a.credential_level,
        trait_manifest=a.trait_manifest.model_dump(),
        constitutional_genome=a.constitutional_genome.model_dump(),
        created_at=a.created_at,
        updated_at=a.updated_at,
        last_training_at=a.last_training_at,
    )


@app.post("/athletes", status_code=status.HTTP_201_CREATED)
def register_athlete(body: AthleteCreate):
    """Register a new athlete in the gym system."""
    athlete = Athlete(
        name=body.name,
        division=body.division,
        tier=body.tier,
        trait_manifest=body.initial_traits or TraitManifest(),
    )
    athlete.created_at = datetime.now(timezone.utc)
    athlete.updated_at = datetime.now(timezone.utc)

    _athletes[athlete.athlete_id] = athlete
    _performance_log[athlete.athlete_id] = []
    _athlete_loads[athlete.athlete_id] = 0.0

    emit_audit(
        actor="system",
        subject=f"athlete:{athlete.athlete_id}",
        action="athlete.created",
        result="success",
        details=f'{{"name": "{athlete.name}", "division": "{athlete.division}", "tier": "{athlete.tier}"}}',
    )
    logger.info("Registered athlete %s (%s)", athlete.name, athlete.athlete_id)
    return _to_athlete_response(athlete)


@app.get("/athletes", response_model=list[RegisterAthleteResponse])
def list_athletes(
    division: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """List all athletes, optionally filtered by division or status."""
    results = list(_athletes.values())

    if division:
        try:
            div_enum = AthleteDivision(division.upper())
            results = [a for a in results if a.division == div_enum]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid division: {division}",
            )

    if status:
        try:
            stat_enum = AthleteStatus(status.upper())
            results = [a for a in results if a.status == stat_enum]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status: {status}",
            )

    return [_to_athlete_response(a) for a in results]


@app.get("/athletes/{athlete_id}")
def get_athlete(athlete_id: str):
    """Retrieve a single athlete by ID."""
    athlete = _athletes.get(athlete_id)
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found",
        )
    return _to_athlete_response(athlete)


@app.patch("/athletes/{athlete_id}/status")
def update_athlete_status(athlete_id: str, new_status: str = Query(...)):
    """Update the operational status of an athlete."""
    athlete = _athletes.get(athlete_id)
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found",
        )

    try:
        parsed = AthleteStatus(new_status.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status: {new_status}. "
                   f"Valid options: {[s.value for s in AthleteStatus]}",
        )

    previous = athlete.status
    athlete.status = parsed
    athlete.updated_at = datetime.now(timezone.utc)

    emit_audit(
        actor="system",
        subject=f"athlete:{athlete.athlete_id}",
        action="athlete.status_changed",
        result="success",
        details=f'{{"from": "{previous}", "to": "{parsed.value}"}}',
    )
    logger.info("Athlete %s status changed: %s -> %s", athlete.name, previous, parsed.value)
    return _to_athlete_response(athlete)


@app.get("/athletes/{athlete_id}/performance", response_model=AthletePerformanceSummary)
def get_athlete_performance(athlete_id: str):
    """Return aggregate performance metrics for an athlete."""
    athlete = _athletes.get(athlete_id)
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found",
        )

    runs = [r for r in _drill_runs.values() if r.athlete_id == athlete_id]
    completed = [r for r in runs if r.status == DrillStatus.COMPLETED]
    scores = [r.score for r in completed]

    return AthletePerformanceSummary(
        athlete_id=athlete_id,
        athlete_name=athlete.name,
        total_runs=len(runs),
        completed_runs=len(completed),
        average_score=round(sum(scores) / len(scores), 4) if scores else 0.0,
        best_score=round(max(scores), 4) if scores else 0.0,
        worst_score=round(min(scores), 4) if scores else 0.0,
        current_load=_athlete_loads.get(athlete_id, 0.0),
        current_tier=athlete.tier,
        division=athlete.division if isinstance(athlete.division, str) else athlete.division.value,
        status=athlete.status if isinstance(athlete.status, str) else athlete.status.value,
        trait_manifest=athlete.trait_manifest.model_dump(),
    )


# ========================== DRILL ENDPOINTS ===============================


@app.post("/drills", response_model=DrillDefinition, status_code=status.HTTP_201_CREATED)
def create_drill(body: DrillCreate):
    """Define a new drill type."""
    try:
        cap_enum = DrillCapability(body.capability.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid capability: {body.capability}. "
                   f"Valid options: {[c.value for c in DrillCapability]}",
        )
    try:
        diff_enum = DrillDifficulty(body.difficulty.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid difficulty: {body.difficulty}. "
                   f"Valid options: {[d.value for d in DrillDifficulty]}",
        )

    drill = DrillDefinition(
        id=f"DRL-{uuid.uuid4().hex[:8].upper()}",
        name=body.name,
        capability=cap_enum,
        difficulty=diff_enum,
        description=body.description,
        created_at=datetime.now(timezone.utc),
    )
    _drills[drill.id] = drill

    emit_audit(
        actor="system",
        subject=f"drill:{drill.id}",
        action="drill.created",
        result="success",
        details=f'{{"name": "{drill.name}", "capability": "{drill.capability.value}", "difficulty": "{drill.difficulty.value}"}}',
    )
    logger.info("Created drill %s (%s)", drill.name, drill.id)
    return drill


@app.post("/drills/{drill_id}/run", response_model=DrillRun, status_code=status.HTTP_201_CREATED)
def run_drill(drill_id: str, athlete_id: str = Query(...)):
    """Execute a drill against an athlete, producing a scored DrillRun."""
    drill = _drills.get(drill_id)
    if not drill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drill {drill_id} not found",
        )

    athlete = _athletes.get(athlete_id)
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found",
        )

    if athlete.status != AthleteStatus.REGISTERED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Athlete {athlete.name} is {athlete.status} — cannot run drills",
        )

    current_load = _athlete_loads.get(athlete_id, 0.0)

    # Simulate execution
    metrics = _compute_drill_score(
        capability=drill.capability,
        traits=athlete.trait_manifest,
        load_level=current_load,
        difficulty=drill.difficulty,
    )

    now = datetime.now(timezone.utc)
    drill_run = DrillRun(
        id=f"RUN-{uuid.uuid4().hex[:8].upper()}",
        drill_id=drill_id,
        athlete_id=athlete_id,
        status=DrillStatus.COMPLETED,
        score=metrics.adjusted_score,
        metrics=metrics,
        started_at=now,
        completed_at=now,
    )
    _drill_runs[drill_run.id] = drill_run

    # Increase load level as a consequence of exertion
    _athlete_loads[athlete_id] = min(1.0, current_load + metrics.load_impact)
    athlete.updated_at = now

    emit_audit(
        actor="system",
        subject=f"drill_run:{drill_run.id}",
        action="drill.run_completed",
        result="success",
        details=(
            f'{{"drill_id": "{drill_id}", "drill_name": "{drill.name}", '
            f'"athlete_id": "{athlete_id}", "athlete_name": "{athlete.name}", '
            f'"score": {drill_run.score}, "capability": "{drill.capability.value}"}}'
        ),
    )
    logger.info(
        "Drill run %s: %s on %s for %s — score=%.4f",
        drill_run.id, drill.name, drill.capability.value, athlete.name, drill_run.score,
    )
    return drill_run


@app.get("/drill-runs/{run_id}", response_model=DrillRun)
def get_drill_run(run_id: str):
    """Retrieve a specific drill run by ID."""
    run = _drill_runs.get(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drill run {run_id} not found",
        )
    return run


@app.get("/athletes/{athlete_id}/drill-runs", response_model=list[DrillRun])
def list_drill_runs(athlete_id: str, limit: int = Query(default=50, ge=1, le=500)):
    """List drill runs for an athlete, most recent first."""
    athlete = _athletes.get(athlete_id)
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found",
        )

    runs = [
        r for r in _drill_runs.values()
        if r.athlete_id == athlete_id
    ]
    runs.sort(
        key=lambda r: r.completed_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return runs[:limit]


# ======================= TRAINING PROGRAM ENDPOINTS ========================


@app.post("/programs", response_model=GymProgram, status_code=status.HTTP_201_CREATED)
def create_program(body: ProgramCreate):
    """Create a training program composed of existing drills."""
    # Validate all drill IDs exist
    missing = [did for did in body.drill_ids if did not in _drills]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Drills not found: {missing}",
        )

    program = GymProgram(
        id=f"PRG-{uuid.uuid4().hex[:8].upper()}",
        name=body.name,
        description=body.description,
        drill_ids=body.drill_ids,
        min_score=body.min_score,
        created_at=datetime.now(timezone.utc),
    )
    _programs[program.id] = program

    emit_audit(
        actor="system",
        subject=f"program:{program.id}",
        action="program.created",
        result="success",
        details=f'{{"name": "{program.name}", "drill_count": {len(program.drill_ids)}, "min_score": {program.min_score}}}',
    )
    logger.info("Created program %s (%s) with %d drills", program.name, program.id, len(body.drill_ids))
    return program


@app.get("/programs", response_model=list[GymProgram])
def list_programs():
    """List all training programs."""
    return list(_programs.values())


# ===================== PERFORMANCE TRACKING ENDPOINTS ======================


@app.post("/athletes/{athlete_id}/performance", status_code=status.HTTP_201_CREATED)
def record_performance(athlete_id: str, metric_name: str = Query(...), value: float = Query(...)):
    """Record an arbitrary performance metric for an athlete."""
    athlete = _athletes.get(athlete_id)
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found",
        )

    record = {
        "metric": metric_name,
        "value": value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _performance_log.setdefault(athlete_id, []).append(record)

    emit_audit(
        actor="system",
        subject=f"athlete:{athlete_id}",
        action="performance.recorded",
        result="success",
        details=f'{{"metric": "{metric_name}", "value": {value}}}',
    )
    logger.info("Performance recorded for %s: %s = %s", athlete.name, metric_name, value)
    return record


@app.get("/athletes/{athlete_id}/performance/history", response_model=PerformanceHistory)
def get_performance_history(athlete_id: str, metric: Optional[str] = Query(None)):
    """Retrieve recorded performance history for an athlete, optionally filtered by metric name."""
    athlete = _athletes.get(athlete_id)
    if not athlete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found",
        )

    records = _performance_log.get(athlete_id, [])
    if metric:
        records = [r for r in records if r["metric"] == metric]

    return PerformanceHistory(
        athlete_id=athlete_id,
        athlete_name=athlete.name,
        records=[PerformanceRecord(**r) for r in records],
        count=len(records),
    )


# =========================== HEALTH CHECK ==================================


@app.get("/health")
def health_check():
    """Simple health probe."""
    return {
        "status": "ok",
        "athletes_registered": len(_athletes),
        "drills_defined": len(_drills),
        "drill_runs_executed": len(_drill_runs),
        "programs_created": len(_programs),
    }
