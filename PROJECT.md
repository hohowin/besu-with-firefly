# PROJECT.md

> Architecture, conventions, and commands. Referenced by `CLAUDE.md` §0, §4, §5. Fill in the TODOs per project.

## Stack

- Language: Python
- Lint: `ruff` · Types: `mypy` · Tests: `pytest`
- Diagrams: Mermaid

## Layers

- `src/core/` — pure logic. No I/O, no side effects (no `print()`, `input()`, `plt.show()`).
- Adapters (CLI, API, MCP) — I/O, formatting, user interaction. Call into core only.
- Tests mirror the structure of the code they cover.
- API handlers are sync (`def`, not `async def`) when they wrap blocking calls.

## Commands

Python 3.11+ (developed on 3.13). Run these from the repo root inside the virtual environment.

| Purpose | Command |
|---|---|
| Create the environment | `python -m venv .venv`, then activate it: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` |
| Install | `pip install -e ".[dev]"` |
| Lint | `ruff check .` |
| Type-check | `mypy .` |
| Unit tests | `pytest` (integration tests are skipped) |
| Integration tests, the gate | `pytest -m "integration and not fault_injection"` (needs Docker and a running stack; about 5 minutes) |
| Integration tests, fault injection | `pytest -m fault_injection` (stops validators; about 5 minutes; can fail on a loaded machine, see `docs/spike-results.md`). `pytest -m integration` runs both |
| Contract packages | `cd contracts && npm ci` (the pinned T-REX and OnchainID artifacts; needed by `deploy` and by some unit tests, which skip without them) |
| Stack | `python scripts/stack.py init\|up\|deploy\|onboard\|reset` (plan D-16). `deploy` and `onboard` only do what is missing |

Lint and type checks skip `spike/`, `.agents/` and `.claude/` (Phase 0 evidence and installed third-party skills). They cover all our own code.

## Directory Layout

```
src/core/          pure logic, no I/O (network/: genesis, enode, health; firefly/: config, keystore, request bodies; trex/: deploy plan, claims, onboarding, amounts)
src/adapters/      I/O: Docker, files, JSON-RPC, the FireFly HTTP client, deploy and onboarding runners, the stack CLI
scripts/           thin entry points (stack.py) that call into src/adapters
tests/unit/        unit tests, mirror src/
tests/integration/ tests that need Docker and a live stack (marker: integration)
tests/support/     helpers for tests (JSON-RPC, FireFly HTTP, polling, deploy)
network-config/    generated genesis, validator keys, static-nodes.json, demo wallets, firefly/ (config and signer keystores) (committed, demo only)
contracts/         package.json pinning the T-REX and OnchainID artifacts (node_modules is not committed)
docker-compose.yml the Besu network and FireFly (Paladin is added in Phase 3)
deployed-addresses.json  addresses written by `deploy` (not committed)
docs/              PRD, architecture, plan, use cases, deliverables, spike results
tasks/             task lists per phase
spike/             Phase 0 evidence (archive, not part of the stack)
perf/              Caliper benchmarks (Phase 5)
```

`perf/` is created by Phase 5.
