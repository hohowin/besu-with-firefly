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
| Integration tests | `pytest -m integration` (needs Docker and, for most of them, a running stack) |
| Stack | `python scripts/stack.py up\|deploy\|reset` (planned, plan D-16; arrives in Phase 1 Task 4 onward) |

Lint and type checks skip `_knowledge/`, `spike/`, `.agents/` and `.claude/` (reference material, Phase 0 evidence and installed third-party skills). They cover all our own code.

## Directory Layout

```
src/core/          pure logic, no I/O (genesis and enode builders, onboarding logic later)
src/adapters/      I/O: Docker, files, JSON-RPC, FireFly HTTP client, CLI
scripts/           thin entry points (stack.py) that call into src/adapters
tests/unit/        unit tests, mirror src/
tests/integration/ tests that need Docker and a live stack (marker: integration)
network-config/    generated genesis, validator keys, static-nodes.json, demo wallets (committed, demo only)
docker-compose.yml the Besu network (FireFly and Paladin are added in later phases)
docs/              PRD, architecture, plan, use cases, deliverables, spike results
tasks/             task lists per phase
spike/             Phase 0 evidence (archive, not part of the stack)
_knowledge/        reference material from an earlier project, deleted when this project is complete
perf/              Caliper benchmarks (Phase 5)
```

Folders for later phases (`network-config/`, `docker-compose.yml`, `perf/`, `scripts/`) are created by their own tasks.
