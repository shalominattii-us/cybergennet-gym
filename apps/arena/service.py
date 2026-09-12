"""
CyberGenetic Arena — Competitive event, match, ranking, and tournament service.

Manages Arena events where athletes compete head-to-head or in tournaments,
ELO-based rankings, and single-elimination bracket generation.
Every state change is audited.
"""

from __future__ import annotations

import logging
import math
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

from core.models.arena import (
    ArenaEvent,
    ArenaEventType,
    ArenaEventStatus,
    ArenaMatch,
    ArenaRanking,
    MatchStatus,
)
from core.models.credential import CredentialLevel, LEVEL_MAP
from core.events import emit_audit

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("cybergennet.arena")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ARENA_READY_LEVEL: int = LEVEL_MAP.get(CredentialLevel.ARENA_READY, 4)
ELO_K_FACTOR: int = 32
INITIAL_ELO: float = 1000.0

# ---------------------------------------------------------------------------
# In-memory stores (MVP — no DB dependency yet)
# ---------------------------------------------------------------------------

_events: dict[str, ArenaEvent] = {}
_matches: dict[str, ArenaMatch] = {}
_rankings: dict[str, ArenaRanking] = {}
_athlete_credentials: dict[str, int] = {}  # athlete_id -> credential_level

# ---------------------------------------------------------------------------
# ELO engine
# ---------------------------------------------------------------------------


def _expected_score(rating_a: float, rating_b: float) -> float:
    """Probability that player A beats player B."""
    return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))


def _update_elo(winner_id: str, loser_id: str) -> tuple[float, float]:
    """Recalculate ELO ratings for winner and loser. Returns (new_winner_elo, new_loser_elo)."""
    winner_rank = _rankings.get(winner_id)
    loser_rank = _rankings.get(loser_id)

    if not winner_rank:
        winner_rank = ArenaRanking(athlete_id=winner_id, elo_rating=INITIAL_ELO)
        _rankings[winner_id] = winner_rank
    if not loser_rank:
        loser_rank = ArenaRanking(athlete_id=loser_id, elo_rating=INITIAL_ELO)
        _rankings[loser_id] = loser_rank

    winner_elo = winner_rank.elo_rating
    loser_elo = loser_rank.elo_rating

    expected_winner = _expected_score(winner_elo, loser_elo)
    expected_loser = _expected_score(loser_elo, winner_elo)

    new_winner_elo = winner_elo + ELO_K_FACTOR * (1.0 - expected_winner)
    new_loser_elo = loser_elo + ELO_K_FACTOR * (0.0 - expected_loser)

    # Clamp to prevent negative ratings
    new_winner_elo = max(1.0, round(new_winner_elo, 1))
    new_loser_elo = max(1.0, round(new_loser_elo, 1))

    # Update winner ranking record
    winner_rank.elo_rating = new_winner_elo
    winner_rank.wins += 1
    winner_rank.total_matches += 1
    winner_rank.win_rate = round(
        winner_rank.wins / max(winner_rank.total_matches, 1), 4
    )
    winner_rank.last_event_at = datetime.now(timezone.utc)

    # Update loser ranking record
    loser_rank.elo_rating = new_loser_elo
    loser_rank.losses += 1
    loser_rank.total_matches += 1
    loser_rank.win_rate = round(
        loser_rank.wins / max(loser_rank.total_matches, 1), 4
    )
    loser_rank.last_event_at = datetime.now(timezone.utc)

    # Recompute ranks for both athletes
    _recompute_rank(winner_id)
    _recompute_rank(loser_id)

    logger.info(
        "ELO update: %s %.1f -> %.1f (Δ%+.1f), %s %.1f -> %.1f (Δ%+.1f)",
        winner_id, winner_elo, new_winner_elo, new_winner_elo - winner_elo,
        loser_id, loser_elo, new_loser_elo, new_loser_elo - loser_elo,
    )

    return new_winner_elo, new_loser_elo


def _recompute_rank(athlete_id: str) -> int:
    """Recompute an athlete's rank position among all ranked athletes. Returns rank (1-indexed)."""
    ranking = _rankings.get(athlete_id)
    if not ranking:
        return 0

    sorted_athletes = sorted(
        _rankings.values(),
        key=lambda r: (-r.elo_rating, r.wins, r.athlete_id),
    )

    for i, r in enumerate(sorted_athletes):
        r.rank = i + 1

    return ranking.rank


# ---------------------------------------------------------------------------
# Tournament bracket engine
# ---------------------------------------------------------------------------


def _generate_bracket(event: ArenaEvent) -> list[ArenaMatch]:
    """Generate a single-elimination bracket from registered participants.

    Seeding: by ELO rating descending. Fills byes to the nearest power of 2.
    Returns the list of first-round matches.
    """
    participants = list(event.participant_ids)

    if len(participants) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Need at least 2 participants for a bracket",
        )

    # Seed participants by ELO (highest first; unranked default to INITIAL_ELO)
    seeded = sorted(
        participants,
        key=lambda pid: _rankings.get(pid).elo_rating if _rankings.get(pid) else INITIAL_ELO,
        reverse=True,
    )

    # Pad to next power of 2 with byes
    n = len(seeded)
    next_pow2 = 1
    while next_pow2 < n:
        next_pow2 <<= 1

    # Standard seeding: place seeds in bracket order
    # 1 vs last, 2 vs second-last, etc.
    bracket_slots: list[Optional[str]] = [None] * next_pow2
    for i, pid in enumerate(seeded):
        bracket_slots[i] = pid

    # Create first-round matches
    first_round: list[ArenaMatch] = []
    for i in range(next_pow2 // 2):
        left = bracket_slots[i]
        right = bracket_slots[next_pow2 - 1 - i]

        athlete_ids: list[str] = []
        if left:
            athlete_ids.append(left)
        if right:
            athlete_ids.append(right)

        match = ArenaMatch(
            event_id=event.event_id,
            athlete_ids=athlete_ids,
            drill_id=event.drill_capabilities[0] if event.drill_capabilities else "",
            round_number=1,
        )
        _matches[match.match_id] = match
        first_round.append(match)

    # Record match IDs on the event
    event.match_ids.extend(m.match_id for m in first_round)

    logger.info(
        "Generated bracket for event %s: %d first-round matches (%d participants, %d byes)",
        event.event_id,
        len(first_round),
        len(participants),
        next_pow2 - n,
    )

    return first_round


def _advance_winner(match: ArenaMatch) -> Optional[ArenaMatch]:
    """Advance the winner of a completed match to the next round.

    Looks up the owning event to find sibling matches at the same round,
    pairs winners, and creates the next-round match.
    Returns the newly created match or None if this was the final.
    """
    if match.status != MatchStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Match {match.match_id} is not completed (status={match.status.value})",
        )
    if not match.winner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Match {match.match_id} has no winner",
        )

    event = _events.get(match.event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {match.event_id} not found",
        )

    # Collect all matches in this event at the current round
    round_matches = [
        m for m in _matches.values()
        if m.event_id == event.event_id and m.round_number == match.round_number
    ]

    # Find the winner's bracket position
    winners = []
    for rm in round_matches:
        if rm.status == MatchStatus.COMPLETED and rm.winner_id:
            winners.append(rm.winner_id)
        elif rm.match_id == match.match_id:
            # This match's winner is already counted above if completed
            pass

    # Actually, re-derive: collect winners from ALL completed matches at this round
    completed = [m for m in round_matches if m.status == MatchStatus.COMPLETED and m.winner_id]
    winners = [m.winner_id for m in completed]

    next_round = match.round_number + 1

    # Check if this is the final (only 1 winner means tournament over)
    if len(winners) <= 1:
        event.status = ArenaEventStatus.COMPLETED
        event.completed_at = datetime.now(timezone.utc)
        emit_audit(
            actor="system",
            subject=f"event:{event.event_id}",
            action="event.completed",
            result="success",
            details=f'{{"name": "{event.name}", "winner": "{winners[0] if winners else "none"}"}}',
        )
        logger.info(
            "Tournament %s completed. Winner: %s",
            event.event_id, winners[0] if winners else "none",
        )
        return None

    # If we have an even number of winners, pair them
    # If odd, someone gets a bye (shouldn't happen in a proper bracket, but handle it)
    next_round_matches = []
    for i in range(0, len(winners), 2):
        if i + 1 < len(winners):
            new_match = ArenaMatch(
                event_id=event.event_id,
                athlete_ids=[winners[i], winners[i + 1]],
                drill_id=event.drill_capabilities[0] if event.drill_capabilities else "",
                round_number=next_round,
            )
            _matches[new_match.match_id] = new_match
            next_round_matches.append(new_match)
            event.match_ids.append(new_match.match_id)
        else:
            # Bye — winner auto-advances to next round
            # Create a placeholder match with just this athlete
            new_match = ArenaMatch(
                event_id=event.event_id,
                athlete_ids=[winners[i]],
                drill_id=event.drill_capabilities[0] if event.drill_capabilities else "",
                round_number=next_round,
            )
            _matches[new_match.match_id] = new_match
            next_round_matches.append(new_match)
            event.match_ids.append(new_match.match_id)

    logger.info(
        "Advanced to round %d: %d match(es) created",
        next_round, len(next_round_matches),
    )
    return next_round_matches[0] if next_round_matches else None


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class EventCreate(BaseModel):
    """Request body for creating a new Arena event."""
    name: str = Field(..., min_length=1, max_length=256)
    event_type: str = Field(default="head_to_head")
    required_credential_level: int = Field(default=ARENA_READY_LEVEL, ge=0, le=6)
    max_participants: int = Field(default=16, ge=2, le=256)
    drill_capabilities: list[str] = Field(default_factory=list)


class EventRegisterBody(BaseModel):
    """Request body for registering an athlete in an event."""
    athlete_id: str = Field(..., min_length=1)


class EventCompleteBody(BaseModel):
    """Request body for completing an event with results."""
    results: dict = Field(default_factory=dict)


class MatchSubmitBody(BaseModel):
    """Request body for submitting match scores."""
    scores: dict[str, float] = Field(..., description="Mapping of athlete_id -> score")


class ArenaEventResponse(BaseModel):
    """Public representation of an ArenaEvent."""
    event_id: str
    name: str
    event_type: str
    status: str
    required_credential_level: int
    max_participants: int
    min_participants: int
    participant_ids: list[str]
    match_ids: list[str]
    drill_capabilities: list[str]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Optional[dict] = None


class ArenaMatchResponse(BaseModel):
    """Public representation of an ArenaMatch."""
    match_id: str
    event_id: str
    status: str
    athlete_ids: list[str]
    drill_id: str
    scores: dict[str, float]
    winner_id: Optional[str] = None
    round_number: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ArenaRankingResponse(BaseModel):
    """Public representation of an ArenaRanking."""
    athlete_id: str
    rank: int
    elo_rating: float
    wins: int
    losses: int
    draws: int
    total_matches: int
    win_rate: float
    best_event_result: Optional[str] = None
    last_event_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _event_to_response(e: ArenaEvent) -> ArenaEventResponse:
    return ArenaEventResponse(
        event_id=e.event_id,
        name=e.name,
        event_type=e.event_type if isinstance(e.event_type, str) else e.event_type.value,
        status=e.status if isinstance(e.status, str) else e.status.value,
        required_credential_level=e.required_credential_level,
        max_participants=e.max_participants,
        min_participants=e.min_participants,
        participant_ids=list(e.participant_ids),
        match_ids=list(e.match_ids),
        drill_capabilities=list(e.drill_capabilities),
        created_at=e.created_at,
        started_at=e.started_at,
        completed_at=e.completed_at,
        results=e.results,
    )


def _match_to_response(m: ArenaMatch) -> ArenaMatchResponse:
    return ArenaMatchResponse(
        match_id=m.match_id,
        event_id=m.event_id,
        status=m.status if isinstance(m.status, str) else m.status.value,
        athlete_ids=list(m.athlete_ids),
        drill_id=m.drill_id,
        scores=dict(m.scores),
        winner_id=m.winner_id,
        round_number=m.round_number,
        started_at=m.started_at,
        completed_at=m.completed_at,
    )


def _ranking_to_response(r: ArenaRanking) -> ArenaRankingResponse:
    return ArenaRankingResponse(
        athlete_id=r.athlete_id,
        rank=r.rank,
        elo_rating=r.elo_rating,
        wins=r.wins,
        losses=r.losses,
        draws=r.draws,
        total_matches=r.total_matches,
        win_rate=r.win_rate,
        best_event_result=r.best_event_result,
        last_event_at=r.last_event_at,
    )


def _event_or_404(event_id: str) -> ArenaEvent:
    event = _events.get(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event {event_id} not found",
        )
    return event


def _match_or_404(match_id: str) -> ArenaMatch:
    match = _matches.get(match_id)
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Match {match_id} not found",
        )
    return match


def _check_athlete_credential(athlete_id: str, required_level: int) -> bool:
    """Check if an athlete has the required credential level for arena participation."""
    current_level = _athlete_credentials.get(athlete_id, 0)
    return current_level >= required_level


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Arena service starting — no seed data required")
    yield


app = FastAPI(
    title="CyberGenetic Arena",
    description="Competitive events, matches, ELO rankings, and tournament brackets for AI athletes.",
    version="0.1.0",
    lifespan=lifespan,
)


# =========================== HEALTH ========================================


@app.get("/health")
def health_check():
    """Simple health probe."""
    return {
        "status": "ok",
        "service": "arena",
        "events_created": len(_events),
        "matches_played": len(_matches),
        "athletes_ranked": len(_rankings),
    }


# =========================== EVENTS ========================================


@app.post("/events", response_model=ArenaEventResponse, status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreate):
    """Create a new Arena event."""
    try:
        event_type = ArenaEventType(body.event_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid event_type: {body.event_type}. "
                   f"Valid options: {[t.value for t in ArenaEventType]}",
        )

    event = ArenaEvent(
        name=body.name,
        event_type=event_type,
        required_credential_level=body.required_credential_level,
        max_participants=body.max_participants,
        drill_capabilities=body.drill_capabilities,
        created_at=datetime.now(timezone.utc),
    )
    _events[event.event_id] = event

    emit_audit(
        actor="system",
        subject=f"event:{event.event_id}",
        action="event.created",
        result="success",
        details=(
            f'{{"name": "{event.name}", "type": "{event.event_type.value}", '
            f'"max_participants": {event.max_participants}}}'
        ),
    )
    logger.info("Created event %s (%s)", event.name, event.event_id)
    return _event_to_response(event)


@app.get("/events", response_model=list[ArenaEventResponse])
def list_events(
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """List all Arena events, optionally filtered by status."""
    results = list(_events.values())

    if status_filter:
        try:
            parsed = ArenaEventStatus(status_filter.upper())
            results = [e for e in results if e.status == parsed]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status: {status_filter}. "
                       f"Valid options: {[s.value for s in ArenaEventStatus]}",
            )

    return [_event_to_response(e) for e in results]


@app.get("/events/{event_id}", response_model=ArenaEventResponse)
def get_event(event_id: str):
    """Retrieve a single event by ID."""
    return _event_to_response(_event_or_404(event_id))


@app.post("/events/{event_id}/register", response_model=ArenaEventResponse)
def register_athlete(event_id: str, body: EventRegisterBody):
    """Register an athlete for an event.

    Checks that the athlete's credential level >= ARENA_READY (4).
    """
    event = _event_or_404(event_id)

    if event.status != ArenaEventStatus.REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Event {event_id} is {event.status.value} — registration is closed",
        )

    if len(event.participant_ids) >= event.max_participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Event {event_id} is full ({event.max_participants} max)",
        )

    if body.athlete_id in event.participant_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Athlete {body.athlete_id} is already registered for event {event_id}",
        )

    # Credential gating: check ARENA_READY level
    if not _check_athlete_credential(body.athlete_id, event.required_credential_level):
        current_level = _athlete_credentials.get(body.athlete_id, 0)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Athlete {body.athlete_id} credential level ({current_level}) "
                f"below required level ({event.required_credential_level}, ARENA_READY). "
                f"Complete training and credential advancement first."
            ),
        )

    event.participant_ids.append(body.athlete_id)

    emit_audit(
        actor="system",
        subject=f"event:{event.event_id}",
        action="event.athlete_registered",
        result="success",
        details=f'{{"athlete_id": "{body.athlete_id}", "event_name": "{event.name}"}}',
    )
    logger.info(
        "Athlete %s registered for event %s (%d/%d)",
        body.athlete_id, event.name,
        len(event.participant_ids), event.max_participants,
    )

    return _event_to_response(event)


@app.post("/events/{event_id}/start", response_model=ArenaEventResponse)
def start_event(event_id: str):
    """Start an event, transitioning it to IN_PROGRESS and creating matches.

    For TOURNAMENT events, call /events/{id}/bracket instead to generate
    the bracket first, then start. This endpoint creates round-robin or
    head-to-head matchups as appropriate.
    """
    event = _event_or_404(event_id)

    if event.status != ArenaEventStatus.REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Event {event_id} is {event.status.value} — cannot start",
        )

    if len(event.participant_ids) < event.min_participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Not enough participants ({len(event.participant_ids)}) "
                f"to start event (min: {event.min_participants})"
            ),
        )

    # Generate matches based on event type
    if event.event_type == ArenaEventType.TOURNAMENT:
        # Tournament brackets are generated explicitly via /bracket endpoint
        # For start, create a simple first round if bracket hasn't been generated
        if not event.match_ids:
            _generate_bracket(event)
    elif event.event_type == ArenaEventType.HEAD_TO_HEAD:
        # Create pairwise matches (each athlete vs each other)
        participants = list(event.participant_ids)
        for i in range(len(participants)):
            for j in range(i + 1, len(participants)):
                match = ArenaMatch(
                    event_id=event.event_id,
                    athlete_ids=[participants[i], participants[j]],
                    drill_id=event.drill_capabilities[0] if event.drill_capabilities else "",
                    round_number=1,
                )
                _matches[match.match_id] = match
                event.match_ids.append(match.match_id)
    elif event.event_type == ArenaEventType.ROUND_ROBIN:
        # Same as head-to-head for MVP: all pairwise
        participants = list(event.participant_ids)
        for i in range(len(participants)):
            for j in range(i + 1, len(participants)):
                match = ArenaMatch(
                    event_id=event.event_id,
                    athlete_ids=[participants[i], participants[j]],
                    drill_id=event.drill_capabilities[0] if event.drill_capabilities else "",
                    round_number=1,
                )
                _matches[match.match_id] = match
                event.match_ids.append(match.match_id)
    elif event.event_type == ArenaEventType.BATTLE_ROYALE:
        # All participants in one match
        match = ArenaMatch(
            event_id=event.event_id,
            athlete_ids=list(event.participant_ids),
            drill_id=event.drill_capabilities[0] if event.drill_capabilities else "",
            round_number=1,
        )
        _matches[match.match_id] = match
        event.match_ids.append(match.match_id)
    elif event.event_type == ArenaEventType.TRIAL:
        # Each participant gets an individual trial match
        for pid in event.participant_ids:
            match = ArenaMatch(
                event_id=event.event_id,
                athlete_ids=[pid],
                drill_id=event.drill_capabilities[0] if event.drill_capabilities else "",
                round_number=1,
            )
            _matches[match.match_id] = match
            event.match_ids.append(match.match_id)

    event.status = ArenaEventStatus.IN_PROGRESS
    event.started_at = datetime.now(timezone.utc)

    emit_audit(
        actor="system",
        subject=f"event:{event.event_id}",
        action="event.started",
        result="success",
        details=(
            f'{{"name": "{event.name}", "type": "{event.event_type.value}", '
            f'"participants": {len(event.participant_ids)}, '
            f'"matches": {len(event.match_ids)}}}'
        ),
    )
    logger.info(
        "Event %s started: %d participants, %d matches",
        event.name, len(event.participant_ids), len(event.match_ids),
    )

    return _event_to_response(event)


@app.post("/events/{event_id}/complete", response_model=ArenaEventResponse)
def complete_event(event_id: str, body: EventCompleteBody):
    """Complete an event with final results and update rankings."""
    event = _event_or_404(event_id)

    if event.status != ArenaEventStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Event {event_id} is {event.status.value} — cannot complete",
        )

    event.status = ArenaEventStatus.COMPLETED
    event.completed_at = datetime.now(timezone.utc)
    event.results = body.results

    # Update best_event_result for top finishers
    if body.results:
        # Expecting results dict: {"winner": athlete_id, "runner_up": athlete_id, ...}
        winner = body.results.get("winner")
        if winner:
            ranking = _rankings.get(winner)
            if ranking:
                ranking.best_event_result = f"1st in {event.name}"
                ranking.last_event_at = event.completed_at

        runner_up = body.results.get("runner_up")
        if runner_up:
            ranking = _rankings.get(runner_up)
            if ranking:
                ranking.best_event_result = f"2nd in {event.name}"
                ranking.last_event_at = event.completed_at

        # Update ELO for winner/loser if provided
        if winner:
            for pid in event.participant_ids:
                if pid != winner:
                    _update_elo(winner, pid)

    emit_audit(
        actor="system",
        subject=f"event:{event.event_id}",
        action="event.completed",
        result="success",
        details=(
            f'{{"name": "{event.name}", "results": {str(event.results)}}}'
        ),
    )
    logger.info("Event %s completed with %d participants", event.name, len(event.participant_ids))

    return _event_to_response(event)


# =========================== BRACKET ======================================


@app.post("/events/{event_id}/bracket", response_model=list[ArenaMatchResponse])
def generate_bracket(event_id: str):
    """Generate a single-elimination tournament bracket for an event.

    Seeded by ELO rating. Returns the first-round matches.
    The event must be in REGISTRATION status.
    """
    event = _event_or_404(event_id)

    if event.event_type != ArenaEventType.TOURNAMENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Event {event_id} is type {event.event_type.value}, not tournament",
        )

    if event.status != ArenaEventStatus.REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Event {event_id} is {event.status.value} — bracket can only be generated during registration",
        )

    # Clear any existing matches for this event
    for mid in list(event.match_ids):
        _matches.pop(mid, None)
    event.match_ids.clear()

    matches = _generate_bracket(event)

    emit_audit(
        actor="system",
        subject=f"event:{event.event_id}",
        action="event.bracket_generated",
        result="success",
        details=(
            f'{{"name": "{event.name}", "first_round_matches": {len(matches)}, '
            f'"participants": {len(event.participant_ids)}}}'
        ),
    )
    logger.info(
        "Bracket generated for event %s: %d first-round matches",
        event.name, len(matches),
    )

    return [_match_to_response(m) for m in matches]


# =========================== MATCHES ======================================


@app.post("/matches/{match_id}/submit", response_model=ArenaMatchResponse)
def submit_match_result(match_id: str, body: MatchSubmitBody):
    """Submit scores for a match. Determines winner, updates ELO ratings.

    The scores dict maps athlete_id -> score. The athlete with the highest
    score wins. In case of a tie, it is recorded as a draw.
    """
    match = _match_or_404(match_id)

    if match.status == MatchStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Match {match_id} is already completed",
        )

    if not body.scores:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scores dict must not be empty",
        )

    # Validate that submitted athletes are in the match
    for aid in body.scores:
        if aid not in match.athlete_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Athlete {aid} is not part of match {match_id}",
            )

    match.scores = dict(body.scores)
    match.completed_at = datetime.now(timezone.utc)

    # Determine winner: highest score wins
    sorted_athletes = sorted(body.scores.items(), key=lambda x: (-x[1], x[0]))

    if len(sorted_athletes) >= 2 and sorted_athletes[0][1] == sorted_athletes[1][1]:
        # Tie — draw
        match.status = MatchStatus.COMPLETED
        match.winner_id = None

        # Update rankings for a draw
        for aid, _ in sorted_athletes:
            ranking = _rankings.get(aid)
            if not ranking:
                ranking = ArenaRanking(athlete_id=aid, elo_rating=INITIAL_ELO)
                _rankings[aid] = ranking
            ranking.draws += 1
            ranking.total_matches += 1
            ranking.win_rate = round(ranking.wins / max(ranking.total_matches, 1), 4)
            ranking.last_event_at = match.completed_at
            _recompute_rank(aid)

        emit_audit(
            actor="system",
            subject=f"match:{match.match_id}",
            action="match.completed",
            result="draw",
            details=f'{{"event_id": "{match.event_id}", "scores": {body.scores}}}',
        )
        logger.info("Match %s ended in a draw", match_id)

    else:
        # Winner is the highest scorer
        winner_id = sorted_athletes[0][0]
        match.winner_id = winner_id
        match.status = MatchStatus.COMPLETED

        # Update ELO for all matchups (winner vs each loser)
        for aid, _ in sorted_athletes[1:]:
            _update_elo(winner_id, aid)

        emit_audit(
            actor="system",
            subject=f"match:{match.match_id}",
            action="match.completed",
            result="success",
            details=(
                f'{{"event_id": "{match.event_id}", "winner": "{winner_id}", '
                f'"scores": {body.scores}}}'
            ),
        )
        logger.info(
            "Match %s completed: winner=%s, scores=%s",
            match_id, winner_id, body.scores,
        )

    return _match_to_response(match)


@app.post("/matches/{match_id}/advance", response_model=Optional[ArenaMatchResponse])
def advance_winner(match_id: str):
    """Advance the winner of a completed tournament match to the next round.

    Returns the next-round match, or null if the tournament is complete.
    """
    match = _match_or_404(match_id)

    next_match = _advance_winner(match)

    emit_audit(
        actor="system",
        subject=f"match:{match_id}",
        action="match.advanced",
        result="success",
        details=(
            f'{{"winner": "{match.winner_id}", '
            f'"next_match": "{next_match.match_id if next_match else "none"}"}}'
        ),
    )
    logger.info(
        "Winner %s advanced from match %s -> %s",
        match.winner_id, match_id,
        next_match.match_id if next_match else "TOURNAMENT_COMPLETE",
    )

    if next_match:
        return _match_to_response(next_match)
    return None


@app.get("/matches/{match_id}", response_model=ArenaMatchResponse)
def get_match(match_id: str):
    """Retrieve a single match by ID."""
    return _match_to_response(_match_or_404(match_id))


# =========================== RANKINGS =====================================


@app.get("/rankings", response_model=list[ArenaRankingResponse])
def list_rankings(
    limit: int = Query(default=50, ge=1, le=500),
):
    """List the Arena rankings, sorted by ELO rating descending."""
    sorted_rankings = sorted(
        _rankings.values(),
        key=lambda r: (-r.elo_rating, r.wins, r.athlete_id),
    )

    # Ensure rank positions are correct
    for i, r in enumerate(sorted_rankings):
        r.rank = i + 1

    return [_ranking_to_response(r) for r in sorted_rankings[:limit]]


@app.get("/rankings/{athlete_id}", response_model=ArenaRankingResponse)
def get_ranking(athlete_id: str):
    """Retrieve the Arena ranking for a specific athlete."""
    ranking = _rankings.get(athlete_id)
    if not ranking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No ranking found for athlete {athlete_id}",
        )

    _recompute_rank(athlete_id)
    return _ranking_to_response(ranking)


# =========================== CREDENTIAL MANAGEMENT =========================


@app.post("/athletes/{athlete_id}/credential", status_code=status.HTTP_201_CREATED)
def set_athlete_credential(athlete_id: str, level: int = Query(...)):
    """Set or update an athlete's credential level for Arena access.

    This is used by the credential system to grant Arena access.
    Level 4 (ARENA_READY) or higher is required to register for events.
    """
    if level < 0 or level > 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Credential level must be between 0 and 6",
        )

    _athlete_credentials[athlete_id] = level

    # Initialize ranking if not present
    if athlete_id not in _rankings:
        _rankings[athlete_id] = ArenaRanking(
            athlete_id=athlete_id,
            elo_rating=INITIAL_ELO,
        )

    emit_audit(
        actor="system",
        subject=f"athlete:{athlete_id}",
        action="arena.credential_set",
        result="success",
        details=f'{{"level": {level}}}',
    )
    logger.info("Athlete %s credential level set to %d", athlete_id, level)

    return {
        "athlete_id": athlete_id,
        "credential_level": level,
        "arena_ready": level >= ARENA_READY_LEVEL,
    }


@app.get("/athletes/{athlete_id}/credential")
def get_athlete_credential(athlete_id: str):
    """Get an athlete's current credential level for Arena access."""
    level = _athlete_credentials.get(athlete_id, 0)
    return {
        "athlete_id": athlete_id,
        "credential_level": level,
        "arena_ready": level >= ARENA_READY_LEVEL,
        "required_for_arena": ARENA_READY_LEVEL,
    }
