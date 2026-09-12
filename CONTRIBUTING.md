# Contributing to CyberGenetic Gym

## Development Setup

```bash
# Clone and install
git clone <repo>
cd cybergennet
pip install -e ".[dev]"

# Run tests
pytest

# Start development server
uvicorn apps.api.main:app --reload
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_athlete.py -v
```

## Adding a New Drill

1. Add the capability to `DrillCapability` enum in `core/models/drill.py`
2. Add scoring logic in `apps/gym/service.py` `_score_drill()` function
3. Add evaluation criteria in `apps/evaluator/service.py`
4. Add tests in `tests/test_drill.py`

## Adding a New Credential Level

1. Add the level to `CredentialLevel` enum in `core/models/credential.py`
2. Update `LEVEL_MAP`
3. Update the documentation in `docs/credential-model.md`

## Adding a New Genetic Operation

1. Add the operation to `GeneticOperation` enum in `core/models/genetic.py`
2. Implement the operation in `apps/genetic/service.py`
3. Add the API endpoint
4. Add tests in `tests/test_genetic.py`

## Constitutional Safety

Every change must verify:
- [ ] Genetic engine never mutates constitutional genome
- [ ] Athletes cannot self-certify evaluation
- [ ] Credentials are scoped and revocable
- [ ] All state changes are audited
- [ ] Default deny network access

## Code Style

- Type hints required on all functions
- Docstrings for public APIs
- Audit events on all state-changing operations
- Tests for all new functionality

## Build Gates

| Gate | Status | Description |
|------|--------|-------------|
| G0-G7 | Complete | MVP: Gym + Evaluation + Credentials + Genetic |
| G8 | Pending | Arena |
| G9 | Pending | SovereignOS integration |
| G10 | Pending | Treasury simulation |
| G11 | Pending | Treasury credential |
| G12 | Pending | Governed live integrations |
