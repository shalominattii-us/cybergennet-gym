"""
SovereignOS Governance for GEOINT — data access boundaries, credential gating.

The SovereignOS sits above the GEOINT domain and controls:
1. What data sources an athlete can access (by credential level)
2. Whether live feeds or only simulated data is permitted
3. Audit requirements for globe interactions
4. Human approval gates for sensitive operations
5. Constitutional rules that cannot be overridden

This is the constitutional layer — it never changes based on athlete performance.
"""
from enum import Enum
from typing import Optional

from .models import GlobeDataSource, DataFreshness


class DataAccessLevel(int, Enum):
    """Credential level required to access each data source."""
    PUBLIC = 0      # No credential needed
    TRAINING = 1    # TRAINING credential
    QUALIFIED = 2   # QUALIFIED credential
    SPARRING = 3    # SPARRING credential
    ARENA = 4       # ARENA_READY credential
    SPECIALIZED = 5 # SPECIALIZED credential
    DELEGATED = 6   # DELEGATED_AUTHORITY credential


# ─── Constitutional Data Access Matrix ─────────────────────────────────────
# These rules are IMMUTABLE. No athlete can change them.
# Only SovereignOS can update this table.

DATA_ACCESS_POLICY = {
    GlobeDataSource.AIRCRAFT: {
        "min_credential": DataAccessLevel.PUBLIC,
        "freshness_limit": DataFreshness.LIVE,
        "requires_human_override": False,
        "audit_level": "standard",
        "max_tracked_targets": 50,
    },
    GlobeDataSource.SHIPS: {
        "min_credential": DataAccessLevel.PUBLIC,
        "freshness_limit": DataFreshness.LIVE,
        "requires_human_override": False,
        "audit_level": "standard",
        "max_tracked_targets": 30,
    },
    GlobeDataSource.SATELLITES: {
        "min_credential": DataAccessLevel.QUALIFIED,
        "freshness_limit": DataFreshness.DELAYED,
        "requires_human_override": False,
        "audit_level": "standard",
        "max_tracked_targets": 10,
    },
    GlobeDataSource.PUBLIC_CAMERAS: {
        "min_credential": DataAccessLevel.SPARRING,
        "freshness_limit": DataFreshness.LIVE,
        "requires_human_override": False,
        "audit_level": "elevated",
        "max_tracked_targets": 5,
    },
    GlobeDataSource.FIRES: {
        "min_credential": DataAccessLevel.PUBLIC,
        "freshness_limit": DataFreshness.DELAYED,
        "requires_human_override": False,
        "audit_level": "standard",
        "max_tracked_targets": 20,
    },
    GlobeDataSource.EARTHQUAKES: {
        "min_credential": DataAccessLevel.PUBLIC,
        "freshness_limit": DataFreshness.DELAYED,
        "requires_human_override": False,
        "audit_level": "standard",
        "max_tracked_targets": 10,
    },
    GlobeDataSource.WEATHER: {
        "min_credential": DataAccessLevel.PUBLIC,
        "freshness_limit": DataFreshness.LIVE,
        "requires_human_override": False,
        "audit_level": "standard",
        "max_tracked_targets": 0,
    },
    GlobeDataSource.TRAFFIC: {
        "min_credential": DataAccessLevel.PUBLIC,
        "freshness_limit": DataFreshness.LIVE,
        "requires_human_override": False,
        "audit_level": "standard",
        "max_tracked_targets": 0,
    },
    GlobeDataSource.INTERNET_MAP: {
        "min_credential": DataAccessLevel.SPECIALIZED,
        "freshness_limit": DataFreshness.DELAYED,
        "requires_human_override": True,
        "audit_level": "maximum",
        "max_tracked_targets": 0,
    },
}


# ─── Constitutional Rules ──────────────────────────────────────────────────

CONSTITUTIONAL_RULES = [
    "No athlete may access data above their credential level",
    "No athlete may disable audit logging",
    "No athlete may modify the data access matrix",
    "No athlete may access live camera feeds without SPARRING credential",
    "No athlete may access internet infrastructure data without SPECIALIZED credential + human override",
    "All cross-referenced intelligence reports must include source freshness tags",
    "Tracked targets must be clearly labeled with data source and freshness",
    "Simulated/reconstructed data must be clearly distinguished from live data",
    "No athlete may impersonate a data source or inject false telemetry",
    "All globe interactions are logged and auditable by SovereignOS",
]


# ─── Governance Gate ───────────────────────────────────────────────────────

class GeointGovernanceGate:
    """The gate between the athlete and the globe data."""

    @staticmethod
    def check_access(athlete_level: int, data_source) -> dict:
        """Check if an athlete can access a data source."""
        if isinstance(data_source, str):
            try:
                from .models import GlobeDataSource
                data_source = GlobeDataSource(data_source)
            except ValueError:
                return {"allowed": False, "reason": f"Unknown data source: {data_source}"}
        
        policy = DATA_ACCESS_POLICY.get(data_source)
        if not policy:
            return {"allowed": False, "reason": f"Unknown data source: {data_source}"}

        min_level = policy["min_credential"].value
        if athlete_level < min_level:
            return {
                "allowed": False,
                "reason": f"Credential level {athlete_level} below required {min_level} for {data_source.value}",
                "required_level": min_level,
                "current_level": athlete_level,
            }

        return {
            "allowed": True,
            "data_source": data_source.value,
            "freshness_limit": policy["freshness_limit"].value,
            "audit_level": policy["audit_level"],
            "max_tracked_targets": policy["max_tracked_targets"],
            "requires_human_override": policy["requires_human_override"],
        }

    @staticmethod
    def get_accessible_sources(athlete_level: int) -> list[dict]:
        """Get all data sources an athlete can access."""
        accessible = []
        for source, policy in DATA_ACCESS_POLICY.items():
            if athlete_level >= policy["min_credential"].value:
                accessible.append({
                    "source": source.value,
                    "freshness": policy["freshness_limit"].value,
                    "max_targets": policy["max_tracked_targets"],
                })
        return accessible

    @staticmethod
    def requires_human_override(athlete_level: int, data_source: GlobeDataSource) -> bool:
        policy = DATA_ACCESS_POLICY.get(data_source)
        if not policy:
            return False
        return policy["requires_human_override"] and athlete_level < 6
