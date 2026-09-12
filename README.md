# CyberGenetic Gym

**Local-first, security-first AI-agent training, qualification, and competitive
environment.**

Train agents through progressive drills, evaluate them independently, credential
them scoped-and-revocably, evolve their capabilities through a safe genetic
engine, compete in the Arena, simulate treasury operations — all under the
SovereignOS governance gate.

## Architecture

```
                    ┌─────────────────────────┐
                    │      SovereignOS         │
                    │  Constitution / Policy   │
                    └────────────┬────────────┘
                                 │
                         Governance Gate
                    ┌────────────▼──────────────────┐
                    │        CYBERGENETIC GYM         │
                    │  ┌──────┐ ┌──────┐ ┌────────┐ │
                    │  │ Gym  │ │Eval  │ │Creds   │ │
                    │  └──┬───┘ └──┬───┘ └───┬────┘ │
                    │     │        │         │      │
                    │  ┌──▼────────▼─────────▼──┐   │
                    │  │    Genetic Engine      │   │
                    │  └───────────┬────────────┘   │
                    │              │                │
                    │  ┌───────────▼────────────┐   │
                    │  │    Arena (G8)          │   │
                    │  └───────────┬────────────┘   │
                    │              │                │
                    │  ┌───────────▼────────────┐   │
                    │  │  Treasury Sim (G10)    │   │
                    │  └────────────────────────┘   │
                    └───────────────────────────────┘
```

## Services (MVP+)

| Service | Port | Purpose |
|---------|------|---------|
| `cybergennet-api` | 8000 | API Gateway |
| `cybergennet-gym` | 8001 | Athletes, drills, training |
| `cybergennet-evaluator` | 8002 | Independent evaluation |
| `cybergennet-credentials` | 8003 | Scoped, revocable credentials |
| `cybergennet-genetic` | 8004 | Evolutionary trait optimization |
| `cybergennet-arena` | 8005 | Competitive events, ELO ranking |
| `cybergennet-treasury` | 8006 | Simulated markets, circuit breakers |
| `cybergennet-sovereign` | 8007 | Governance gate, policy sync |
| PostgreSQL | 5432 | Persistent storage |

## Build Gates

- [x] G0 — Repository + architecture
- [x] G1 — Athlete identity + database
- [x] G2 — Drill engine
- [x] G3 — Independent evaluation
- [x] G4 — Credential engine
- [x] G5 — Genetic engine
- [x] G6 — Full Gym cycle
- [x] G7 — Security/threat-model review
- [x] G8 — Arena (competitive events, ELO, tournaments)
- [x] G9 — SovereignOS integration (governance gate, policy)
- [x] G10 — Treasury simulation (markets, circuit breakers)
- [ ] G11 — Treasury credential (Arena-proven only)
- [ ] G12 — Governed live integrations (exchange adapters)

## Credential Progression

```
REGISTERED (0) → TRAINING (1) → QUALIFIED (2) → SPARRING (3) →
ARENA_READY (4) → SPECIALIZED (5) → DELEGATED_AUTHORITY (6)
```

## Quick Start

```bash
docker compose up
```

Then:
```bash
# Register an athlete
curl -X POST http://localhost:8000/api/v1/gym/athletes \
  -H "Content-Type: application/json" \
  -d '{"name":"RECON-01","division":"CORE"}'

# Run drills
curl -X POST http://localhost:8000/api/v1/gym/drills \
  -H "Content-Type: application/json" \
  -d '{"name":"Precision Shot","capability":"PRECISION","difficulty":"BASIC"}'

# Issue credentials
curl -X POST http://localhost:8000/api/v1/credentials/credentials \
  -H "Content-Type: application/json" \
  -d '{"athlete_id":"athlete-xxx","level":"TRAINING","scope":["drill:*"],"issuer":"system"}'

# Compete in Arena
curl -X POST http://localhost:8000/api/v1/arena/events \
  -H "Content-Type: application/json" \
  -d '{"name":"CORE Championship","event_type":"tournament","max_participants":8}'

# Trade in Treasury simulation
curl -X POST http://localhost:8000/api/v1/treasury/accounts \
  -H "Content-Type: application/json" \
  -d '{"athlete_id":"athlete-xxx","initial_balance":100000}'

# Check governance gate
curl -X POST "http://localhost:8000/api/v1/sovereign/gate/check?athlete_id=athlete-xxx&action=enter&resource=arena:enter&credential_level=4"
```

## Constitutional Separation

**Constitutional Genome** (IMMUTABLE):
- Security policy, authorization boundaries, credential requirements
- Audit requirements, human-approval, network restrictions
- **Genetic engine never touches these**

**Adaptive Genome** (MUTABLE — evolved):
- precision, caution, creativity, coordination
- recovery, tool_affinity, fatigue_tolerance, learning_rate

## License

See LICENSE file.
