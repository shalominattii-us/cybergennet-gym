"""
Provenance tracking — hash-linked audit trail.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime


def compute_environment_hash() -> str:
    """Compute a hash of the current environment fingerprint."""
    raw = json.dumps({
        "schema_version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def compute_provenance_hash(previous_hash: str, event_data: dict) -> str:
    """Hash-link an event to the previous event for chain integrity."""
    raw = json.dumps({
        "previous_hash": previous_hash,
        **event_data,
    }, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()
