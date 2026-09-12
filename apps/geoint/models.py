"""
GEOINT (Geospatial Intelligence) training domain — drills, data sources, and scoring.

Integrates God's Eye View globe data with CyberGenetic Gym credentialing.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ─── Data Sources (God's Eye View layers) ─────────────────────────────────

class GlobeDataSource(str, Enum):
    AIRCRAFT = "aircraft"             # Live ADS-B flight tracking
    SHIPS = "ships"                   # Live AIS maritime tracking
    SATELLITES = "satellites"         # Orbital element propagation
    PUBLIC_CAMERAS = "public_cameras" # Webcam / CCTV feeds
    EARTHQUAKES = "earthquakes"       # USGS seismic data
    FIRES = "fires"                   # Satellite fire detection (FIRMS)
    WEATHER = "weather"               # Live weather layers
    TRAFFIC = "traffic"               # Road traffic data
    INTERNET_MAP = "internet_map"     # Physical internet infrastructure


class DataFreshness(str, Enum):
    LIVE = "live"                     # Real-time feed
    DELAYED = "delayed"               # 1-5 min behind real-time
    SIMULATED = "simulated"           # Modeled / reconstructed
    HISTORICAL = "historical"         # Past event playback
    UNAVAILABLE = "unavailable"       # Feed down / out of coverage


class GlobeCoordinate(BaseModel):
    lat: float
    lng: float
    alt_m: float = 0.0


class GlobeBounds(BaseModel):
    """Bounding box for a training scenario."""
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float
    label: str = ""


# ─── GEOINT Drill Types ──────────────────────────────────────────────────

class GeointCapability(str, Enum):
    RECONNAISSANCE = "reconnaissance"           # Find & track specific targets
    SITUATIONAL_AWARENESS = "situational_awareness"  # Maintain multi-target awareness
    RAPID_RESPONSE = "rapid_response"           # Detect & react to changes
    SPATIAL_REASONING = "spatial_reasoning"     # Navigate, predict trajectories
    DATA_FUSION = "data_fusion"                 # Cross-reference multiple sources


class TargetType(str, Enum):
    AIRCRAFT = "aircraft"
    SHIP = "ship"
    SATELLITE = "satellite"
    FIRE = "fire"
    EARTHQUAKE = "earthquake"
    CAMERA = "camera"
    ROUTE = "route"
    BOUNDARY = "boundary"
    ANOMALY = "anomaly"


class GeointScenario(BaseModel):
    """A training scenario on the globe."""

    scenario_id: str = Field(default_factory=lambda: f"geo-{uuid.uuid4().hex[:8]}")
    name: str
    capability: GeointCapability
    description: str
    data_sources: list[GlobeDataSource] = Field(default_factory=list)
    bounds: Optional[GlobeBounds] = None
    targets: list[dict] = Field(default_factory=list)
    time_limit_seconds: int = 300
    difficulty: str = "T3"
    version: str = "1.0.0"


class GeointDrillRun(BaseModel):
    """Result of a single GEOINT drill execution."""

    run_id: str = Field(default_factory=lambda: f"georun-{uuid.uuid4().hex[:8]}")
    scenario_id: str
    athlete_id: str
    capability: GeointCapability
    status: str = "PENDING"

    # Core metrics
    targets_found: int = 0
    targets_total: int = 0
    accuracy: float = 0.0          # Correct identifications / total
    completion_time_ms: int = 0
    coverage_pct: float = 0.0      # % of search area covered

    # Advanced metrics
    false_positives: int = 0
    missed_targets: int = 0
    trajectory_error_m: float = 0.0  # Avg deviation for tracked targets
    response_time_ms: int = 0        # For rapid response drills
    fusion_accuracy: float = 0.0     # For data fusion drills

    # Trail
    path_taken: list[GlobeCoordinate] = Field(default_factory=list)
    detections: list[dict] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)

    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
