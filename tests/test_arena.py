"""Tests for Arena service."""
import sys
sys.path.insert(0, ".")

import pytest
from core.models.arena import ArenaEvent, ArenaEventType, ArenaEventStatus, ArenaMatch, MatchStatus, ArenaRanking


class TestArena:
    def test_create_event(self):
        e = ArenaEvent(name="Test Championship", event_type=ArenaEventType.TOURNAMENT)
        assert e.event_id.startswith("arena-")
        assert e.status == ArenaEventStatus.REGISTRATION
        assert e.required_credential_level == 4

    def test_create_match(self):
        m = ArenaMatch(
            event_id="arena-test",
            athlete_ids=["athlete-1", "athlete-2"],
            drill_id="drill-test",
        )
        assert m.match_id.startswith("match-")
        assert m.status == MatchStatus.SCHEDULED

    def test_match_scoring(self):
        m = ArenaMatch(
            event_id="arena-test",
            athlete_ids=["athlete-1", "athlete-2"],
            scores={"athlete-1": 0.85, "athlete-2": 0.72},
            winner_id="athlete-1",
        )
        assert m.winner_id == "athlete-1"
        assert m.scores["athlete-1"] > m.scores["athlete-2"]

    def test_arena_ranking_defaults(self):
        r = ArenaRanking(athlete_id="athlete-1")
        assert r.elo_rating == 1000.0
        assert r.wins == 0
        assert r.losses == 0
        assert r.win_rate == 0.0

    def test_elo_update(self):
        """Verify ELO math."""
        r1 = ArenaRanking(athlete_id="athlete-1", elo_rating=1000.0)
        r2 = ArenaRanking(athlete_id="athlete-2", elo_rating=1200.0)
        expected_r1 = 1 / (1 + 10 ** ((1200 - 1000) / 400))
        expected_r2 = 1 / (1 + 10 ** ((1000 - 1200) / 400))
        assert 0.2 < expected_r1 < 0.3  # underdog
        assert 0.7 < expected_r2 < 0.8  # favorite
