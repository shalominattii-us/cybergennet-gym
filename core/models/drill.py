"""CyberGenetic Gym — Drill and program domain models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DrillCapability(str, Enum):
    PRECISION = "PRECISION"
    REACTION = "REACTION"
    CONDITIONING = "CONDITIONING"
    RECOVERY = "RECOVERY"
    INTEGRATION = "INTEGRATION"


class DrillDifficulty(str, Enum):
    BASIC = "BASIC"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    ELITE = "ELITE"


class DrillStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DrillDefinition(BaseModel):
    """A defined drill that can be run against athletes."""
    id: str = Field(default_factory=lambda: f"DRL-{uuid.uuid4().hex[:8].upper()}")
    name: str
    capability: DrillCapability
    difficulty: DrillDifficulty = DrillDifficulty.BASIC
    description: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DrillRunMetrics(BaseModel):
    """Scoring metrics produced by a drill run."""
    raw_score: float = 0.0
    adjusted_score: float = 0.0
    recovery_time_ms: float = 0.0
    load_impact: float = 0.0
    fatigue_factor: float = 0.0


class DrillRun(BaseModel):
    """A single execution of a drill by an athlete."""
    id: str = Field(default_factory=lambda: f"RUN-{uuid.uuid4().hex[:8].upper()}")
    drill_id: str
    athlete_id: str
    status: DrillStatus = DrillStatus.PENDING
    score: float = 0.0
    metrics: DrillRunMetrics = Field(default_factory=DrillRunMetrics)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class GymProgram(BaseModel):
    """A curated training program composed of multiple drills."""
    id: str = Field(default_factory=lambda: f"PRG-{uuid.uuid4().hex[:8].upper()}")
    name: str
    description: str = ""
    drill_ids: list[str] = Field(default_factory=list)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
