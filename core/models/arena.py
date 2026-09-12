"""
Arena models — competitive events, tournaments, and rankings.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ArenaEventType(str, Enum):
    HEAD_TO_HEAD = "head_to_head"
    ROUND_ROBIN = "round_robin"
    TOURNAMENT = "tournament"
    BATTLE_ROYALE = "battle_royale"
    TRIAL = "trial"


class ArenaEventStatus(str, Enum):
    REGISTRATION = "REGISTRATION"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class MatchStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FORFEIT = "FORFEIT"
    CANCELLED = "CANCELLED"


class ArenaEvent(BaseModel):
    """A competitive event in the Arena."""

    event_id: str = Field(default_factory=lambda: f"arena-{uuid.uuid4().hex[:8]}")
    name: str
    event_type: ArenaEventType
    status: ArenaEventStatus = ArenaEventStatus.REGISTRATION
    required_credential_level: int = 4  # ARENA_READY
    max_participants: int = 16
    min_participants: int = 2
    participant_ids: list[str] = Field(default_factory=list)
    match_ids: list[str] = Field(default_factory=list)
    drill_capabilities: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Optional[dict] = None


class ArenaMatch(BaseModel):
    """A single match within an Arena event."""

    match_id: str = Field(default_factory=lambda: f"match-{uuid.uuid4().hex[:8]}")
    event_id: str
    status: MatchStatus = MatchStatus.SCHEDULED
    athlete_ids: list[str] = Field(default_factory=list)
    drill_id: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    winner_id: Optional[str] = None
    round_number: int = 1
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ArenaRanking(BaseModel):
    """Arena ranking entry for an athlete."""

    athlete_id: str
    rank: int = 0
    elo_rating: float = 1000.0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    total_matches: int = 0
    win_rate: float = 0.0
    best_event_result: Optional[str] = None
    last_event_at: Optional[datetime] = None
