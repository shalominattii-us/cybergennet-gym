# Threat Model — CyberGenetic Gym v0.1

## Scope

This threat model covers the CyberGenetic Gym MVP (services, credentials,
genetic engine, evaluation). Arena, Treasury, and SovereignOS integration
are out of scope for v0.1 and will have their own threat models.

## Trust Model

| Component | Trust Level | Rationale |
|-----------|-------------|-----------|
| System operators | Trusted | Configure and maintain the Gym |
| Athlete agents | Untrusted | Cannot self-certify, no network access |
| Evaluator service | Trusted | Independent, system-controlled |
| Credential service | Trusted | Issues and verifies credentials |
| Genetic engine | Trusted-but-restricted | Never mutates constitutional genome |
| External model providers | Untrusted | Future integration; treated as adversarial |

## Assets

- Athlete identities and trait manifests
- Credentials and authorization state
- Evaluation scores and performance history
- Audit logs (tamper-evident)
- Constitutional genome (integrity critical)
- System configuration and secrets

## Threats

### T1: Constitutional genome mutation
**Risk:** HIGH
**Mitigation:** Genetic engine verifies constitutional hash before every
operation. Any constitutional field mutation attempt is logged as a security
event and rejected. Verify function compares field-by-field.

### T2: Athlete self-certification
**Risk:** HIGH
**Mitigation:** Evaluation is always performed by an independent evaluator
service. Athletes cannot submit evaluations. Multi-evaluator mode requires
primary + secondary evaluator agreement. Flag for human adjudication on
disagreement > 0.2.

### T3: Credential escalation
**Risk:** HIGH
**Mitigation:** Credentials are scoped and revocable. Each credential has a
maximum risk level. Every action checks credential level + scope. Revocation
is immediate. Audit trail for all credential operations.

### T4: Unauthorized network access
**Risk:** MEDIUM
**Mitigation:** Default deny network policy. Athletes have no egress access
unless explicitly granted through a specialized credential. Network adapters
are explicit interfaces.

### T5: Secrets exposure
**Risk:** MEDIUM
**Mitigation:** No secrets are exposed to athletes. All secrets live in the
system layer. Athlete workspaces are isolated from system configuration.

### T6: Genetic algorithm convergence/fragility
**Risk:** LOW (safety), MEDIUM (effectiveness)
**Mitigation:** Diversity pressure prevents population convergence.
Selection uses fitness + novelty + robustness + recovery, not fitness alone.
Minimum diversity threshold enforced.

### T7: Audit log tampering
**Risk:** MEDIUM
**Mitigation:** Audit events include provenance_hash linking to previous event.
Any gap or mismatch in the chain indicates tampering. Events include
policy_version and environment_hash for reproducibility.

### T8: Denial of service against evaluator
**Risk:** LOW
**Mitigation:** In MVP, evaluator runs in-process with resource limits.
Production: rate limiting, separate evaluator pool, request queuing.

## Assumptions

1. The system runs in a trusted environment (local/Docker).
2. PostgreSQL is configured with encryption at rest.
3. Network between services is trusted (Docker internal network).
4. Human operators with credential admin access are trusted.
5. No external API dependencies for core Gym operation.

## Out of Scope (v0.1)

- Arena competitive events
- Treasury operations
- SovereignOS integration
- Public token minting
- Live financial execution
- External model provider integration
- SOC 2 / ISO certification

## Future Threats (G8+)

- Arena poisoning attacks
- Treasury replay attacks
- SovereignOS privilege escalation via Gym
- Model provider prompt injection
- Cross-athlete data leakage in sparring
