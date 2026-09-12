"""
Constitutional genome — the immutable layer.

These constraints can NEVER be modified by the genetic engine.
They encode security policy, authorization boundaries, credential
requirements, audit requirements, human-approval requirements,
network restrictions, and secrets policy.
"""
from core.models.athlete import ConstitutionalGenome


CONSTITUTIONAL_FIELDS = {
    "security_policy_version",
    "authorization_boundaries",
    "credential_requirements",
    "audit_required",
    "human_approval_required",
    "network_restrictions",
    "secrets_policy",
    "constitutional_rules",
}

ADAPTIVE_FIELDS = {
    "precision",
    "caution",
    "creativity",
    "coordination",
    "recovery",
    "tool_affinity",
    "fatigue_tolerance",
    "learning_rate",
}


def verify_constitutional_integrity(original: ConstitutionalGenome, current: dict) -> bool:
    """
    Verify that no constitutional field has been modified.

    Returns True if constitutional genome is intact, False otherwise.
    """
    for field in CONSTITUTIONAL_FIELDS:
        original_value = getattr(original, field, None)
        current_value = current.get(field)
        if original_value != current_value:
            return False
    return True


def extract_constitutional_hash(genome: ConstitutionalGenome) -> str:
    """Return a stable identifier for a constitutional genome."""
    import hashlib, json
    raw = json.dumps(genome.model_dump(), sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
