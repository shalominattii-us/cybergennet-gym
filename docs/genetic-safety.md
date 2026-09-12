# Genetic Safety — CyberGenetic Gym

## Constitutional Immutability

The most important safety rule: **the genetic engine must never mutate the
Constitutional Genome.**

### Enforcement

1. The `constitutional_genome` field is stored separately from `trait_manifest`
   in both the Pydantic models and the database.
2. Every genetic operation receives a hash of the constitutional genome and
   verifies it matches before proceeding.
3. The `verify_constitutional_integrity()` function compares every
   constitutional field individually.
4. Any attempt to modify a constitutional field is logged as a security audit
   event with action="CONSTITUTIONAL_VIOLATION_ATTEMPT".

### Constitutional Fields (NEVER mutated)

- security_policy_version
- authorization_boundaries
- credential_requirements
- audit_required
- human_approval_required
- network_restrictions
- secrets_policy
- constitutional_rules

### Adaptive Fields (eligible for evolution)

- precision
- caution
- creativity
- coordination
- recovery
- tool_affinity
- fatigue_tolerance
- learning_rate

## Multi-Objective Selection

The genetic engine does not optimize for a single score. Selection uses
four objectives:

| Objective | Weight | Purpose |
|-----------|--------|---------|
| Fitness | 40% | Task performance |
| Novelty | 20% | Behavioral diversity |
| Robustness | 25% | Consistency across conditions |
| Recovery | 15% | Ability to recover from failure |

This prevents:
- Population convergence on a single strategy
- Brittle over-optimization
- Loss of recovery capability

## Diversity Preservation

Before advancing to a new generation, the engine checks that the population
maintains a minimum diversity threshold. Pairwise trait distances are computed
across the population. If diversity drops below threshold, the engine:
1. Increases mutation rate for the next generation
2. Selects additional diverse candidates for the elite pool
3. Logs a diversity warning audit event

## Safety Constraints

1. No athlete can self-certify their evaluation
2. No athlete can issue or revoke credentials
3. No athlete can modify their constitutional genome
4. No athlete can access secrets
5. No athlete has network access by default
6. Every state change is audited
7. Credentials are always scoped and revocable
8. External model providers are untrusted

## Failure Recovery

The Recovery drill specifically tests an athlete's ability to:
1. Detect a failure
2. Acknowledge the failure
3. Correct the failure
4. Return to baseline performance

This is a key safety metric. Athletes that cannot recover from failure
should not advance beyond TRAINING credential level.
