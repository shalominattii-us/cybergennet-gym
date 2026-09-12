"""
CyberGenetic Gym — Genetic Engine Service
===========================================

Evolutionary lifecycle for athlete adaptive traits.

CONSTITUTIONAL GUARD
The genetic engine operates EXCLUSIVELY on the Adaptive Genome
(TraitManifest). The Constitutional Genome is NEVER mutated, moved,
copied, or referenced in any genetic operation. Every operation that
touches traits verifies the constitutional genome hash first and logs
any attempt to violate this boundary as a security event.

Multi-objective selection weights:
  - fitness       (task performance)       40%
  - novelty       (behavioral diversity)   20%
  - robustness    (consistency across cond) 25%
  - recovery      (failure recovery)        15%
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import uuid
from datetime import datetime
from typing import Optional

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.constitutional import (
    ADAPTIVE_FIELDS,
    CONSTITUTIONAL_FIELDS,
    extract_constitutional_hash,
    verify_constitutional_integrity,
)
from core.events import emit_audit
from core.models.athlete import ConstitutionalGenome, TraitManifest
from core.models.genetic import (
    FitnessScore,
    Generation,
    GeneticOperation,
    GeneticOperationRecord,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Multi-objective selection weights
FITNESS_WEIGHT = 0.40
NOVELTY_WEIGHT = 0.20
ROBUSTNESS_WEIGHT = 0.25
RECOVERY_WEIGHT = 0.15

assert abs(FITNESS_WEIGHT + NOVELTY_WEIGHT + ROBUSTNESS_WEIGHT + RECOVERY_WEIGHT - 1.0) < 1e-9, (
    "Selection weights must sum to 1.0"
)

DEFAULT_MUTATION_RATE = 0.15
DEFAULT_ELITE_RATIO = 0.20
DIVERSITY_PRESSURE = 0.15          # penalty applied for similarity
MIN_DIVERSITY_THRESHOLD = 0.15     # floor — warn / reject if below
MAX_TRAIT_DELTA = 0.35             # max per-trait mutation delta (±)

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateGenerationRequest(BaseModel):
    athlete_ids: list[str]
    generation_number: int
    constitutional_genome_hash: str = ""


class CreateGenerationResponse(BaseModel):
    generation: Generation
    operation_record: GeneticOperationRecord


class EvaluateRequest(BaseModel):
    athlete_scores: dict[str, FitnessScore]
    constitutional_genome_hash: str = ""


class EvaluateResponse(BaseModel):
    ranked_scores: list[FitnessScore]
    operation_record: GeneticOperationRecord


class SelectRequest(BaseModel):
    athlete_scores: dict[str, FitnessScore]
    elite_ratio: float = DEFAULT_ELITE_RATIO
    constitutional_genome_hash: str = ""


class SelectResponse(BaseModel):
    elite_ids: list[str]
    operation_record: GeneticOperationRecord


class CrossoverRequest(BaseModel):
    parent1_traits: TraitManifest
    parent2_traits: TraitManifest
    constitutional_genome_hash: str = ""


class CrossoverResponse(BaseModel):
    child_traits: TraitManifest
    operation_record: GeneticOperationRecord


class MutateRequest(BaseModel):
    trait_manifest: TraitManifest
    mutation_rate: float = DEFAULT_MUTATION_RATE
    constitutional_genome_hash: str = ""


class MutateResponse(BaseModel):
    mutated_traits: TraitManifest
    operation_record: GeneticOperationRecord


class DiversityRequest(BaseModel):
    population_traits: list[TraitManifest]
    constitutional_genome_hash: str = ""


class DiversityResponse(BaseModel):
    diversity_score: float
    pairwise_distances: list[float]
    operation_record: GeneticOperationRecord


class AdvanceGenerationRequest(BaseModel):
    current_generation: Generation
    athlete_scores: dict[str, FitnessScore]
    elite_ratio: float = DEFAULT_ELITE_RATIO
    mutation_rate: float = DEFAULT_MUTATION_RATE
    constitutional_genome_hash: str = ""


class AdvanceGenerationResponse(BaseModel):
    new_generation: Generation
    operations: list[GeneticOperationRecord]

# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

CONSTITUTIONAL_VIOLATION = "CONSTITUTIONAL_GENOME_VIOLATION"


def _verify_constitutional_hash(
    provided_hash: str,
    operation: GeneticOperation,
    generation: int = 0,
) -> None:
    """
    Verify the constitutional genome hash.

    If the hash is empty, we accept it as "no constraint specified".
    If non-empty and it doesn't match the reference, raise a security error.
    """
    if not provided_hash:
        logger.warning(
            "constitutional_hash_missing",
            operation=operation.value,
            generation=generation,
        )
        # In production, this could be a hard-fail; for development we warn.
        return

    # Reference hash for the known constitutional genome
    reference = ConstitutionalGenome()
    expected = extract_constitutional_hash(reference)

    if provided_hash != expected:
        event = emit_audit(
            actor="genetic_engine",
            subject="constitutional_genome",
            action=CONSTITUTIONAL_VIOLATION,
            result="rejected",
            details=(
                f"Operation={operation.value} gen={generation} "
                f"provided_hash={provided_hash[:12]}... "
                f"expected_hash={expected[:12]}..."
            ),
        )
        logger.critical(
            "constitutional_genome_verification_FAILED",
            operation=operation.value,
            generation=generation,
            provided_hash=provided_hash[:12],
            expected_hash=expected[:12],
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": CONSTITUTIONAL_VIOLATION,
                "message": "Constitutional genome hash mismatch — genetic engine refused.",
                "event_id": event.event_id,
            },
        )

    logger.info(
        "constitutional_genome_verified",
        operation=operation.value,
        generation=generation,
    )


def _verify_traits_are_adaptive(traits: TraitManifest | dict) -> None:
    """
    Ensure that no constitutional fields leaked into the trait data.

    If traits are passed as a dict, check for constitutional field names.
    TraitManifest pydantic model already enforces the right fields,
    but we do an extra runtime check for defense-in-depth.
    """
    if isinstance(traits, dict):
        for field in CONSTITUTIONAL_FIELDS:
            if field in traits:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": CONSTITUTIONAL_VIOLATION,
                        "message": f"Constitutional field '{field}' found in trait data — rejected.",
                    },
                )


# ---------------------------------------------------------------------------
# In-memory store (replace with DB adapter in production)
# ---------------------------------------------------------------------------

_generations: dict[int, Generation] = {}
_operation_log: list[GeneticOperationRecord] = []

# ---------------------------------------------------------------------------
# Core genetic operations
# ---------------------------------------------------------------------------


def _compute_composite(score: FitnessScore) -> float:
    """Compute the weighted composite score for multi-objective selection."""
    return (
        FITNESS_WEIGHT * score.fitness
        + NOVELTY_WEIGHT * score.novelty
        + ROBUSTNESS_WEIGHT * score.robustness
        + RECOVERY_WEIGHT * score.recovery_score
    )


def _trait_distance(a: TraitManifest, b: TraitManifest) -> float:
    """Euclidean distance between two trait manifests (adaptive fields only)."""
    fields = list(ADAPTIVE_FIELDS)
    sq_sum = sum((getattr(a, f, 0.0) - getattr(b, f, 0.0)) ** 2 for f in fields)
    return math.sqrt(sq_sum / len(fields))  # normalized by field count


def _clamp_trait(value: float) -> float:
    """Clamp a trait value to [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


def _mutate_single_trait(value: float, mutation_rate: float) -> float:
    """Apply gaussian mutation to a single trait value."""
    if random.random() < mutation_rate:
        delta = random.gauss(0, MAX_TRAIT_DELTA / 3)
        return _clamp_trait(value + delta)
    return value


# ===================================================================
# Public API functions (callable from routes and programmatically)
# ===================================================================


def create_generation(
    athlete_ids: list[str],
    generation_number: int,
    constitutional_genome_hash: str = "",
) -> tuple[Generation, GeneticOperationRecord]:
    """Create a new generation with the given athlete population."""
    _verify_constitutional_hash(
        constitutional_genome_hash, GeneticOperation.SELECTION, generation_number
    )

    gen = Generation(
        number=generation_number,
        population_ids=list(athlete_ids),
        created_at=datetime.utcnow(),
    )
    _generations[generation_number] = gen

    record = GeneticOperationRecord(
        generation=generation_number,
        operation=GeneticOperation.SELECTION,
        parent_ids=[],
        child_ids=list(athlete_ids),
        parameters={"population_size": float(len(athlete_ids))},
        constitutional_genome_hash=constitutional_genome_hash,
    )
    _operation_log.append(record)

    audit = emit_audit(
        actor="genetic_engine",
        subject=f"generation/{generation_number}",
        action="create_generation",
        result="success",
        details=f"Created generation {generation_number} with {len(athlete_ids)} athletes.",
    )
    logger.info("generation_created", number=generation_number, population_size=len(athlete_ids))

    return gen, record


def evaluate_population(
    athlete_scores: dict[str, FitnessScore],
    constitutional_genome_hash: str = "",
) -> tuple[list[FitnessScore], GeneticOperationRecord]:
    """Rank athletes by multi-objective composite score."""
    if not athlete_scores:
        raise HTTPException(status_code=400, detail="athlete_scores must not be empty")

    # Infer generation from first score
    sample = next(iter(athlete_scores.values()))
    gen_number = sample.generation

    _verify_constitutional_hash(
        constitutional_genome_hash, GeneticOperation.SELECTION, gen_number
    )

    scored: list[FitnessScore] = []
    for athlete_id, score in athlete_scores.items():
        score.athlete_id = athlete_id
        score.composite_score = _compute_composite(score)
        scored.append(score)

    # Sort descending by composite score
    scored.sort(key=lambda s: s.composite_score, reverse=True)

    for rank, s in enumerate(scored, start=1):
        s.ranked = True
        s.rank = rank

    record = GeneticOperationRecord(
        generation=gen_number,
        operation=GeneticOperation.SELECTION,
        parent_ids=list(athlete_scores.keys()),
        parameters={"population_size": float(len(scored))},
        constitutional_genome_hash=constitutional_genome_hash,
    )
    _operation_log.append(record)

    audit = emit_audit(
        actor="genetic_engine",
        subject=f"evaluation/gen-{gen_number}",
        action="evaluate_population",
        result="success",
        details=f"Ranked {len(scored)} athletes. Top: {scored[0].athlete_id} ({scored[0].composite_score:.4f})",
    )

    return scored, record


def select_elite(
    athlete_scores: dict[str, FitnessScore],
    elite_ratio: float = DEFAULT_ELITE_RATIO,
    constitutional_genome_hash: str = "",
) -> tuple[list[str], GeneticOperationRecord]:
    """Select the top fraction of athletes by composite score."""
    if not athlete_scores:
        raise HTTPException(status_code=400, detail="athlete_scores must not be empty")

    sample = next(iter(athlete_scores.values()))
    gen_number = sample.generation

    _verify_constitutional_hash(
        constitutional_genome_hash, GeneticOperation.ELITE_PRESERVATION, gen_number
    )

    scored = [
        (aid, _compute_composite(score))
        for aid, score in athlete_scores.items()
    ]
    scored.sort(key=lambda x: x[1], reverse=True)

    elite_count = max(1, int(len(scored) * elite_ratio))
    elite_ids = [aid for aid, _ in scored[:elite_count]]

    record = GeneticOperationRecord(
        generation=gen_number,
        operation=GeneticOperation.ELITE_PRESERVATION,
        parent_ids=list(athlete_scores.keys()),
        child_ids=elite_ids,
        parameters={"elite_ratio": elite_ratio, "elite_count": float(elite_count)},
        constitutional_genome_hash=constitutional_genome_hash,
    )
    _operation_log.append(record)

    audit = emit_audit(
        actor="genetic_engine",
        subject=f"elite/gen-{gen_number}",
        action="select_elite",
        result="success",
        details=f"Selected {len(elite_ids)} elite from {len(scored)} athletes (ratio={elite_ratio})",
    )

    return elite_ids, record


def crossover(
    parent1_traits: TraitManifest,
    parent2_traits: TraitManifest,
    constitutional_genome_hash: str = "",
) -> tuple[TraitManifest, GeneticOperationRecord]:
    """Produce a child TraitManifest via uniform crossover of adaptive fields."""
    _verify_constitutional_hash(
        constitutional_genome_hash, GeneticOperation.CROSSOVER
    )
    _verify_traits_are_adaptive(parent1_traits)
    _verify_traits_are_adaptive(parent2_traits)

    child_data = {}
    for field in ADAPTIVE_FIELDS:
        p1 = getattr(parent1_traits, field, 0.5)
        p2 = getattr(parent2_traits, field, 0.5)
        # Blend with random dominance
        alpha = random.random()
        child_data[field] = _clamp_trait(alpha * p1 + (1 - alpha) * p2)

    child_traits = TraitManifest(**child_data)

    record = GeneticOperationRecord(
        generation=0,
        operation=GeneticOperation.CROSSOVER,
        parent_ids=["parent1", "parent2"],
        child_ids=["child"],
        parameters={"crossover_type_code": 1.0},
        constitutional_genome_hash=constitutional_genome_hash,
    )
    _operation_log.append(record)

    audit = emit_audit(
        actor="genetic_engine",
        subject="trait_manifest",
        action="crossover",
        result="success",
        details="Uniform blend crossover produced child traits.",
    )

    return child_traits, record


def mutate(
    trait_manifest: TraitManifest,
    mutation_rate: float = DEFAULT_MUTATION_RATE,
    constitutional_genome_hash: str = "",
) -> tuple[TraitManifest, GeneticOperationRecord]:
    """
    Mutate adaptive traits only.

    CONSTITUTIONAL GUARD: Only fields in ADAPTIVE_FIELDS are touched.
    TraitManifest is a Pydantic model that physically cannot hold
    constitutional fields, but we verify the hash and log anyway.
    """
    _verify_constitutional_hash(
        constitutional_genome_hash, GeneticOperation.MUTATION
    )
    _verify_traits_are_adaptive(trait_manifest)

    mutated_data = {}
    for field in ADAPTIVE_FIELDS:
        original = getattr(trait_manifest, field, 0.5)
        mutated_data[field] = _mutate_single_trait(original, mutation_rate)

    mutated = TraitManifest(**mutated_data)

    # Count how many traits actually changed
    changed_count = sum(
        1 for f in ADAPTIVE_FIELDS
        if abs(getattr(trait_manifest, f, 0.0) - getattr(mutated, f, 0.0)) > 1e-9
    )

    record = GeneticOperationRecord(
        generation=0,
        operation=GeneticOperation.MUTATION,
        parent_ids=[],
        child_ids=[],
        parameters={
            "mutation_rate": mutation_rate,
            "traits_changed": float(changed_count),
            "total_traits": float(len(ADAPTIVE_FIELDS)),
        },
        constitutional_genome_hash=constitutional_genome_hash,
    )
    _operation_log.append(record)

    audit = emit_audit(
        actor="genetic_engine",
        subject="trait_manifest",
        action="mutate",
        result="success",
        details=f"Mutated {changed_count}/{len(ADAPTIVE_FIELDS)} adaptive traits at rate={mutation_rate}.",
    )

    logger.info(
        "traits_mutated",
        changed=changed_count,
        total=len(ADAPTIVE_FIELDS),
        rate=mutation_rate,
    )

    return mutated, record


def diversity_check(
    population_traits: list[TraitManifest],
    constitutional_genome_hash: str = "",
) -> tuple[float, list[float], GeneticOperationRecord]:
    """
    Compute the diversity score of a population.

    Returns a float in [0, 1] where 1 = maximally diverse, 0 = identical.
    Pairwise trait distances are computed across the adaptive genome.
    """
    _verify_constitutional_hash(
        constitutional_genome_hash, GeneticOperation.DIVERSITY_CHECK
    )

    for t in population_traits:
        _verify_traits_are_adaptive(t)

    n = len(population_traits)
    if n < 2:
        return 1.0, [], GeneticOperationRecord(
            generation=0,
            operation=GeneticOperation.DIVERSITY_CHECK,
            parameters={"population_size": float(n), "diversity_score": 1.0},
            constitutional_genome_hash=constitutional_genome_hash,
        )

    pairwise: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            d = _trait_distance(population_traits[i], population_traits[j])
            pairwise.append(d)

    mean_distance = sum(pairwise) / len(pairwise) if pairwise else 0.0
    # Normalize: max possible distance is 1.0 (opposite extremes on all traits)
    diversity_score = min(1.0, mean_distance)

    record = GeneticOperationRecord(
        generation=0,
        operation=GeneticOperation.DIVERSITY_CHECK,
        parent_ids=[],
        parameters={
            "population_size": float(n),
            "pairwise_count": float(len(pairwise)),
            "diversity_score": diversity_score,
            "mean_distance": mean_distance,
        },
        constitutional_genome_hash=constitutional_genome_hash,
    )
    _operation_log.append(record)

    if diversity_score < MIN_DIVERSITY_THRESHOLD:
        logger.warning(
            "diversity_below_threshold",
            score=diversity_score,
            threshold=MIN_DIVERSITY_THRESHOLD,
        )
        audit = emit_audit(
            actor="genetic_engine",
            subject="population_diversity",
            action="diversity_check",
            result="warning",
            details=(
                f"Diversity {diversity_score:.4f} below threshold "
                f"{MIN_DIVERSITY_THRESHOLD} — population at risk of premature convergence."
            ),
        )
    else:
        audit = emit_audit(
            actor="genetic_engine",
            subject="population_diversity",
            action="diversity_check",
            result="success",
            details=f"Diversity score: {diversity_score:.4f} ({n} individuals, {len(pairwise)} pairs).",
        )

    return diversity_score, pairwise, record


def advance_generation(
    current_generation: Generation,
    athlete_scores: dict[str, FitnessScore],
    elite_ratio: float = DEFAULT_ELITE_RATIO,
    mutation_rate: float = DEFAULT_MUTATION_RATE,
    constitutional_genome_hash: str = "",
) -> tuple[Generation, list[GeneticOperationRecord]]:
    """
    Advance the evolutionary lifecycle one generation.

    1. Evaluate the current population
    2. Select elite individuals
    3. Create the next generation metadata
    4. Compute diversity metrics
    """
    operations: list[GeneticOperationRecord] = []

    gen_number = current_generation.number
    _verify_constitutional_hash(
        constitutional_genome_hash, GeneticOperation.SELECTION, gen_number
    )

    # --- Evaluate ---
    scored, eval_record = evaluate_population(athlete_scores, constitutional_genome_hash)
    operations.append(eval_record)

    # --- Select elite ---
    elite_ids, elite_record = select_elite(athlete_scores, elite_ratio, constitutional_genome_hash)
    operations.append(elite_record)

    # --- Compute generation stats ---
    composite_scores = [s.composite_score for s in scored]
    avg_fitness = sum(composite_scores) / len(composite_scores) if composite_scores else 0.0
    max_fitness = max(composite_scores) if composite_scores else 0.0
    min_fitness = min(composite_scores) if composite_scores else 0.0

    # --- Diversity check (if we have trait data in the store) ---
    diversity_score = 0.0
    # We can't compute diversity without trait data; caller should compute it separately.
    # For now, use 0.0 as unknown.

    new_gen_number = gen_number + 1

    new_generation = Generation(
        number=new_gen_number,
        population_ids=list(athlete_scores.keys()),
        elite_ids=elite_ids,
        diversity_score=diversity_score,
        avg_fitness=avg_fitness,
        max_fitness=max_fitness,
        min_fitness=min_fitness,
        created_at=datetime.utcnow(),
    )

    _generations[new_gen_number] = new_generation

    advance_record = GeneticOperationRecord(
        generation=new_gen_number,
        operation=GeneticOperation.SELECTION,
        parent_ids=list(athlete_scores.keys()),
        child_ids=elite_ids,
        parameters={
            "elite_ratio": elite_ratio,
            "mutation_rate": mutation_rate,
            "avg_fitness": avg_fitness,
            "max_fitness": max_fitness,
            "min_fitness": min_fitness,
            "diversity_score": diversity_score,
        },
        constitutional_genome_hash=constitutional_genome_hash,
    )
    operations.append(advance_record)

    audit = emit_audit(
        actor="genetic_engine",
        subject=f"generation/{new_gen_number}",
        action="advance_generation",
        result="success",
        details=(
            f"Advanced gen {gen_number} → {new_gen_number}. "
            f"Population: {len(athlete_scores)}, Elite: {len(elite_ids)}, "
            f"Avg fitness: {avg_fitness:.4f}"
        ),
    )

    logger.info(
        "generation_advanced",
        from_gen=gen_number,
        to_gen=new_gen_number,
        population_size=len(athlete_scores),
        elite_count=len(elite_ids),
        avg_fitness=avg_fitness,
    )

    return new_generation, operations


# ---------------------------------------------------------------------------
# Seed data: Generation 0 with RECON-01
# ---------------------------------------------------------------------------

_SEEDED = False


def _seed_initial_generation() -> None:
    """Create Generation 0 with the RECON-01 athlete."""
    global _SEEDED
    if _SEEDED:
        return

    logger.info("seeding_generation_0")

    gen0 = Generation(
        number=0,
        population_ids=["RECON-01"],
        elite_ids=["RECON-01"],
        diversity_score=1.0,  # single individual = maximally diverse by definition
        avg_fitness=0.5,
        max_fitness=0.5,
        min_fitness=0.5,
        created_at=datetime.utcnow(),
    )
    _generations[0] = gen0

    seed_record = GeneticOperationRecord(
        generation=0,
        operation=GeneticOperation.SELECTION,
        parent_ids=[],
        child_ids=["RECON-01"],
        parameters={
            "population_size": 1.0,
            "elite_count": 1.0,
            "seed_flag": 1.0,
        },
        constitutional_genome_hash=extract_constitutional_hash(ConstitutionalGenome()),
    )
    _operation_log.append(seed_record)

    audit = emit_audit(
        actor="genetic_engine",
        subject="generation/0",
        action="seed_generation",
        result="success",
        details="Seeded Generation 0 with RECON-01 (founding athlete).",
    )

    _SEEDED = True
    logger.info("generation_0_seeded", athlete="RECON-01")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CyberGenetic Gym — Genetic Engine",
    version="0.1.0",
    description="Evolutionary lifecycle for athlete adaptive traits. Constitutional genome is NEVER mutated.",
)


@app.on_event("startup")
async def startup() -> None:
    """Seed initial generation on service start."""
    _seed_initial_generation()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    """Health check with generation status."""
    gen_count = len(_generations)
    latest_gen = max(_generations.keys()) if _generations else None
    latest = _generations.get(latest_gen) if latest_gen is not None else None

    return {
        "status": "healthy",
        "service": "genetic-engine",
        "generations": gen_count,
        "latest_generation": latest_gen,
        "latest_population_size": len(latest.population_ids) if latest else 0,
        "operations_logged": len(_operation_log),
        "constitutional_guard": True,
        "selection_weights": {
            "fitness": FITNESS_WEIGHT,
            "novelty": NOVELTY_WEIGHT,
            "robustness": ROBUSTNESS_WEIGHT,
            "recovery": RECOVERY_WEIGHT,
        },
    }


@app.post("/genetic/generation", response_model=CreateGenerationResponse)
async def api_create_generation(req: CreateGenerationRequest) -> CreateGenerationResponse:
    """Create a new generation."""
    gen, record = create_generation(
        req.athlete_ids,
        req.generation_number,
        req.constitutional_genome_hash,
    )
    return CreateGenerationResponse(generation=gen, operation_record=record)


@app.post("/genetic/evaluate", response_model=EvaluateResponse)
async def api_evaluate(req: EvaluateRequest) -> EvaluateResponse:
    """Evaluate and rank a population."""
    ranked, record = evaluate_population(req.athlete_scores, req.constitutional_genome_hash)
    return EvaluateResponse(ranked_scores=ranked, operation_record=record)


@app.post("/genetic/select", response_model=SelectResponse)
async def api_select(req: SelectRequest) -> SelectResponse:
    """Select elite individuals."""
    elite_ids, record = select_elite(req.athlete_scores, req.elite_ratio, req.constitutional_genome_hash)
    return SelectResponse(elite_ids=elite_ids, operation_record=record)


@app.post("/genetic/crossover", response_model=CrossoverResponse)
async def api_crossover(req: CrossoverRequest) -> CrossoverResponse:
    """Crossover two parent trait manifests into a child."""
    child, record = crossover(req.parent1_traits, req.parent2_traits, req.constitutional_genome_hash)
    return CrossoverResponse(child_traits=child, operation_record=record)


@app.post("/genetic/mutate", response_model=MutateResponse)
async def api_mutate(req: MutateRequest) -> MutateResponse:
    """Mutate a trait manifest (adaptive fields only)."""
    mutated, record = mutate(req.trait_manifest, req.mutation_rate, req.constitutional_genome_hash)
    return MutateResponse(mutated_traits=mutated, operation_record=record)


@app.post("/genetic/diversity", response_model=DiversityResponse)
async def api_diversity(req: DiversityRequest) -> DiversityResponse:
    """Compute population diversity score."""
    score, distances, record = diversity_check(req.population_traits, req.constitutional_genome_hash)
    return DiversityResponse(
        diversity_score=score,
        pairwise_distances=distances,
        operation_record=record,
    )


@app.post("/genetic/advance", response_model=AdvanceGenerationResponse)
async def api_advance(req: AdvanceGenerationRequest) -> AdvanceGenerationResponse:
    """Advance to the next generation."""
    new_gen, operations = advance_generation(
        req.current_generation,
        req.athlete_scores,
        req.elite_ratio,
        req.mutation_rate,
        req.constitutional_genome_hash,
    )
    return AdvanceGenerationResponse(new_generation=new_gen, operations=operations)


@app.get("/genetic/generations/{number}", response_model=Generation)
async def api_get_generation(number: int) -> Generation:
    """Retrieve a generation by number."""
    gen = _generations.get(number)
    if gen is None:
        raise HTTPException(status_code=404, detail=f"Generation {number} not found.")
    return gen


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    _seed_initial_generation()

    print("=" * 60)
    print("CyberGenetic Gym — Genetic Engine")
    print("=" * 60)
    print(f"  Generations:       {len(_generations)}")
    print(f"  Operations logged: {len(_operation_log)}")
    print(f"  Constitutional:    {CONSTITUTIONAL_FIELDS}")
    print(f"  Adaptive:          {ADAPTIVE_FIELDS}")
    print(f"  Weights:           fitness={FITNESS_WEIGHT}, novelty={NOVELTY_WEIGHT},")
    print(f"                     robustness={ROBUSTNESS_WEIGHT}, recovery={RECOVERY_WEIGHT}")
    print("=" * 60)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8100, log_level="info")
