"""
Security policies — default-deny authorization framework.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AuthorizationDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class Policy(BaseModel):
    """A single policy rule."""
    resource: str
    action: str
    decision: AuthorizationDecision
    condition: Optional[str] = None  # future: expression evaluator
    policy_version: str = "1.0.0"


# Default policies
DEFAULT_POLICIES: list[Policy] = [
    Policy(resource="gym:enter", action="access", decision=AuthorizationDecision.ALLOW),
    Policy(resource="drill:execute", action="run", decision=AuthorizationDecision.ALLOW,
           condition="credential_level >= 1"),
    Policy(resource="drill:precision", action="run", decision=AuthorizationDecision.ALLOW),
    Policy(resource="drill:reaction", action="run", decision=AuthorizationDecision.ALLOW),
    Policy(resource="drill:conditioning", action="run", decision=AuthorizationDecision.ALLOW),
    Policy(resource="drill:recovery", action="run", decision=AuthorizationDecision.ALLOW),
    Policy(resource="evaluation:self-certify", action="submit", decision=AuthorizationDecision.DENY),
    Policy(resource="credential:issue", action="admin", decision=AuthorizationDecision.REQUIRE_APPROVAL),
    Policy(resource="credential:revoke", action="admin", decision=AuthorizationDecision.REQUIRE_APPROVAL),
    Policy(resource="genetic:mutate-constitutional", action="modify",
           decision=AuthorizationDecision.DENY),
    Policy(resource="network:egress", action="connect", decision=AuthorizationDecision.DENY),
    Policy(resource="secrets:read", action="access", decision=AuthorizationDecision.DENY),
]


def evaluate_policy(resource: str, action: str, credential_level: int = 0) -> AuthorizationDecision:
    """Evaluate a policy decision."""
    for policy in DEFAULT_POLICIES:
        if policy.resource == resource and policy.action == action:
            if policy.condition:
                # Simple condition evaluator
                if "credential_level >= " in policy.condition:
                    required = int(policy.condition.split(">= ")[1])
                    if credential_level < required:
                        return AuthorizationDecision.DENY
            return policy.decision

    # Default: deny
    return AuthorizationDecision.DENY
