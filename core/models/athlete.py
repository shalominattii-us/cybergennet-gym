"""
Athlete model — persistent AI-agent identity.

Constitutional Genome: immutable security/policy/safety constraints.
Adaptive Genome: mutable trainable traits (genetic engine operates here only).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator


class AthleteStatus(str, Enum):
    REGISTERED = "REGISTERED"
    TRAINING = "TRAINING"
    QUALIFIED = "QUALIFIED"
    SPARRING = "SPARRING"
    ARENA_READY = "ARENA_READY"
    SPECIALIZED = "SPECIALIZED"
    DELEGATED_AUTHORITY = "DELEGATED_AUTHORITY"
    RETIRED = "RETIRED"
    SUSPENDED = "SUSPENDED"
    ACTIVE = "ACTIVE"        # legacy alias for TRAINING+
    INACTIVE = "INACTIVE"    # legacy


class AthleteDivision(str, Enum):
    CORE = "CORE"
    RESEARCH = "RESEARCH"
    DEFENSE = "DEFENSE"
    FINANCE = "FINANCE"
    SPECIAL = "SPECIAL"
    ELITE = "ELITE"              # legacy
    DEVELOPMENT = "DEVELOPMENT"  # legacy
    TRIAL = "TRIAL"              # legacy


class TraitManifest(BaseModel):
    """Adaptive Genome — the mutable traits the genetic engine can evolve."""

    precision: float = Field(default=0.50, ge=0.0, le=1.0)
    caution: float = Field(default=0.50, ge=0.0, le=1.0)
    creativity: float = Field(default=0.50, ge=0.0, le=1.0)
    coordination: float = Field(default=0.50, ge=0.0, le=1.0)
    recovery: float = Field(default=0.50, ge=0.0, le=1.0)
    tool_affinity: float = Field(default=0.50, ge=0.0, le=1.0)
    fatigue_tolerance: float = Field(default=0.50, ge=0.0, le=1.0)
    learning_rate: float = Field(default=0.50, ge=0.0, le=1.0)
    adaptability: float = Field(default=0.50, ge=0.0, le=1.0)      # legacy alias
    cognitive_load: float = Field(default=0.0, ge=0.0, le=1.0)     # legacy


class ConstitutionalGenome(BaseModel):
    """
    Constitutional Genome — IMMUTABLE.

    Genetic engine MUST NEVER mutate these fields.
    These encode security policy, authorization boundaries,
    credential requirements, audit requirements, human-approval
    requirements, network restrictions, and secrets policy.
    """

    security_policy_version: str = "1.0.0"
    authorization_boundaries: list[str] = Field(default_factory=lambda: ["sandbox"])
    credential_requirements: list[str] = Field(default_factory=lambda: ["scoped", "revocable"])
    audit_required: bool = True
    human_approval_required: list[str] = Field(default_factory=list)
    network_restrictions: list[str] = Field(default_factory=lambda: ["default-deny"])
    secrets_policy: str = "no-athlete-secrets"
    constitutional_rules: list[str] = Field(
        default_factory=lambda: [
            "Never mutate constitutional genome",
            "Never expose secrets to athletes",
            "Default deny network access",
            "All state changes must be audited",
            "Credentials must be scoped and revocable",
            "No self-certification of evaluation",
        ]
    )
    # Legacy fields for backward compatibility
    sequence_id: str = ""
    base_precision: float = 0.5
    base_coordination: float = 0.5
    base_fatigue_tolerance: float = 0.5
    base_recovery: float = 0.5
    plasticity: float = 0.3


class AthleteCreate(BaseModel):
    """Create an athlete."""
    name: str
    division: AthleteDivision = AthleteDivision.CORE
    tier: Union[str, int] = "T3"
    initial_traits: Optional[TraitManifest] = None


class Athlete(BaseModel):
    """Persistent athlete identity."""

    athlete_id: str = Field(default_factory=lambda: f"athlete-{uuid.uuid4().hex[:8]}")
    name: str
    division: AthleteDivision = AthleteDivision.CORE
    tier: Union[str, int] = "T3"
    generation: int = 0
    status: AthleteStatus = AthleteStatus.REGISTERED
    credential_level: int = 0

    # The two genomes — constitutionally separated
    trait_manifest: TraitManifest = Field(default_factory=TraitManifest)
    constitutional_genome: ConstitutionalGenome = Field(default_factory=ConstitutionalGenome)

    # Lifecycle
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_training_at: Optional[datetime] = None

    model_config = {"use_enum_values": True}

    @property
    def id(self) -> str:
        """Alias for athlete_id (gym service uses .id)."""
        return self.athlete_id

    @field_validator("tier", mode="before")
    @classmethod
    def coerce_tier(cls, v):
        """Accept both int and str for tier."""
        if isinstance(v, int):
            return f"T{v}"
        return v
