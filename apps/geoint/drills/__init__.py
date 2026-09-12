"""
GEOINT Drills — 5 core training capabilities on the God's Eye View globe.

Each drill tests a specific geospatial intelligence skill with clear metrics.
"""
from .recon import ReconnaissanceDrill
from .situational import SituationalAwarenessDrill
from .response import RapidResponseDrill
from .spatial import SpatialReasoningDrill
from .fusion import DataFusionDrill

DRILL_REGISTRY = {
    "reconnaissance": ReconnaissanceDrill,
    "situational_awareness": SituationalAwarenessDrill,
    "rapid_response": RapidResponseDrill,
    "spatial_reasoning": SpatialReasoningDrill,
    "data_fusion": DataFusionDrill,
}
