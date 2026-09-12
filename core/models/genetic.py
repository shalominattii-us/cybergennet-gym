"""
Genetic engine models — evolutionary lifecycle for adaptive traits.

Operates ONLY on the Adaptive Genome (TraitManifest).
NEVER on the Constitutional Genome.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class GeneticOperation(str, Enum):
    SELECTION = "selection"
    CROSSOVER = "crossover"
    MUTATION = "mutation"
    ELITE_PRESERVATION = "elite_preservation"
    DIVERSITY_CHECK = "diversity_check"
    RETIREMENT = "retirement"
    ARCHIVAL = "archival"


class Generation(BaseModel):
    """A generation in the evolutionary lifecycle."""

    generation_id: str = Field(default_factory=lambda: f"gen-{uuid.uuid4().hex[:8]}")
    number: int
    population_ids: list[str] = Field(default_factory=list)
    elite_ids: list[str] = Field(default_factory=list)
    diversity_score: float = 0.0
    avg_fitness: float = 0.0
    max_fitness: float = 0.0
    min_fitness: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GeneticOperationRecord(BaseModel):
    """Audit trail for each genetic operation."""

    operation_id: str = Field(default_factory=lambda: f"gop-{uuid.uuid4().hex[:8]}")
    generation: int
    operation: GeneticOperation
    parent_ids: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, float] = Field(default_factory=dict)
    constitutional_genome_hash: str = ""  # verify it was never touched
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FitnessScore(BaseModel):
    """Multi-dimensional fitness for selection."""

    athlete_id: str
    generation: int

    # Primary metrics
    fitness: float = 0.0      # weighted composite
    novelty: float = 0.0      # diversity pressure
    robustness: float = 0.0   # consistency across conditions
    recovery_score: float = 0.0  # recovery ability

    # Composite
    composite_score: float = 0.0  # fitness + novelty_weight*novelty + ...

    ranked: bool = False
    rank: Optional[int] = None
