# Credential Model — CyberGenetic Gym

## Philosophy

Credentials in CyberGenetic Gym follow three principles:

1. **Credential ≠ trust.** A credential grants access to a capability, but
   does not imply the athlete is "trusted" in any general sense.
2. **Authentication ≠ authorization.** Proving identity does not grant access
   to any capability beyond what the credential explicitly allows.
3. **Authorization ≠ correctness.** Even with authorized access, the athlete's
   output must be independently verified.

## Credential Structure

```json
{
  "credential_id": "cred-abc123",
  "athlete_id": "athlete-0001",
  "level": "TRAINING",
  "scope": ["drill:precision", "drill:reaction"],
  "maximum_risk": "low",
  "issued_by": "system",
  "issued_at": "2026-09-12T00:00:00Z",
  "expires_at": "2026-10-12T00:00:00Z",
  "evidence_hash": "sha256:...",
  "revocable": true,
  "revoked": false,
  "revoked_at": null,
  "revocation_reason": null
}
```

## Credential Levels

| Level | Name | Privilege | Requirement |
|-------|------|-----------|-------------|
| 0 | REGISTERED | Enter the Gym | None |
| 1 | TRAINING | Execute sandboxed drills | Registered |
| 2 | QUALIFIED | Demonstrated baseline reliability | Pass all basic drills |
| 3 | SPARRING | Interact with other agents | Qualified + evaluation |
| 4 | ARENA_READY | Competitive events | Sparring + multi-eval |
| 5 | SPECIALIZED | Narrowly scoped tools | Arena + human approval |
| 6 | DELEGATED_AUTHORITY | Bounded operational authority | Specialized + governance |

## Scope Model

Each credential has a `scope` field — a list of resource:action pairs
the credential authorizes:

- `drill:*` — all drills
- `drill:precision` — precision drills only
- `evaluation:*` — all evaluation access
- `network:egress` — outbound network access (requires DELEGATED_AUTHORITY)
- `treasury:read` — read treasury state (future)
- `treasury:execute` — execute treasury operations (future)

## Risk Levels

- `none` — No risk (viewing data)
- `low` — Minimal risk (running drills)
- `medium` — Moderate risk (agent interaction)
- `high` — Significant risk (tool access)
- `critical` — Highest risk (operational authority)

## Lifecycle

```
Issue → Active → Expired
                → Revoked (immediate)
                → Re-issued (upgrade/downgrade)
```

## Verification Flow

1. Actor presents credential_id + requested action
2. System checks credential exists and is not revoked
3. System checks credential level >= required level
4. System checks action is within credential scope
5. System checks risk level is within credential's maximum_risk
6. System checks credential has not expired
7. If all pass → ALLOW; otherwise → DENY + audit event

## Audit

Every credential operation (issue, revoke, verify, expire) produces a
CredentialEvent recorded in the credential_events table and the global
audit_events table.
