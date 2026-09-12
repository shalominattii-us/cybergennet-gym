# Architecture — CyberGenetic Gym

## Overview

CyberGenetic Gym is a local-first, security-first training and qualification
environment for AI agents. It implements constitutional separation between
immutable security constraints and mutable trainable traits, with a gated
credential system that prevents agents from accessing capabilities they
haven't earned.

## Design Principles

1. **Constitutional Separation** — The genetic engine never mutates security
   policy, authorization boundaries, or any constitutional constraint.
2. **No Self-Certification** — Athletes cannot grade their own performance.
   Evaluation is always independent.
3. **Default Deny** — No athlete has any access unless explicitly granted.
4. **Progressive Credentialing** — Capabilities are unlocked through demonstrated
   reliability, not assumed.
5. **Audit Everything** — Every state-changing action produces an immutable-style
   audit event.
6. **Local First** — The system operates without requiring external APIs.
   Provider adapters allow Ollama/Groq/etc. later.

## Service Architecture

```
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│  API Gateway │  │  Gym Service  │  │  Evaluator    │
│  (port 8000) │──│  (port 8001)  │  │  (port 8002)  │
└─────────────┘  └──────┬───────┘  └──────┬───────┘
                        │                  │
              ┌─────────▼──────┐  ┌───────▼─────────┐
              │  Credentials   │  │  Genetic Engine  │
              │  (port 8003)   │  │  (port 8004)     │
              └─────────┬──────┘  └───────┬─────────┘
                        │                  │
                        └────────┬─────────┘
                                 │
                        ┌────────▼────────┐
                        │   PostgreSQL    │
                        │   (port 5432)   │
                        └─────────────────┘
```

## Data Flow

1. Athlete registers → Gym creates identity with constitutional + adaptive genomes
2. Athlete runs drill → Gym records run with scoring
3. Drill run → Evaluator produces independent score (athlete cannot self-certify)
4. Performance meets threshold → Credentials issues/upgrades credential
5. Population trained → Genetic engine selects, crosses, mutates (adaptive only)
6. New generation → Back to Gym for next training cycle

## Constitutional vs Adaptive Genome

### Constitutional (IMMUTABLE)
- security_policy_version
- authorization_boundaries
- credential_requirements
- audit_required
- human_approval_required
- network_restrictions
- secrets_policy
- constitutional_rules

### Adaptive (MUTABLE — evolved by genetic engine)
- precision
- caution
- creativity
- coordination
- recovery
- tool_affinity
- fatigue_tolerance
- learning_rate

## Security Boundaries

- Default deny: all athlete network access is denied by default
- Workspace isolation: each athlete has an isolated workspace
- No athlete secrets: secrets never enter athlete-accessible memory
- External providers: model providers are treated as untrusted
- Credential verification: every action checks scope + level + revocation
- Audit chain: events are hash-linked for tamper evidence
