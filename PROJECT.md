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
| Integration tests | `pytest -m integration` (needs Docker and a running stack; about 13 minutes) |
| Contract packages | `cd contracts && npm ci` (the pinned T-REX and OnchainID artifacts; needed by `deploy` and by some unit tests, which skip without them) |
| CLI | `besu-ff query\|invoke\|tx\|register` (after `pip install -e ".[dev]"`; needs `up` and `deploy`; `besu-ff --help`) |
| Stack | `python scripts/stack.py init\|up\|deploy\|onboard\|noto-demo\|reset` (plan D-16). `deploy` and `onboard` only do what is missing; `noto-demo` needs `deploy` and deploys a new Noto token each run |

Lint and type checks skip `spike/`, `.agents/` and `.claude/` (Phase 0 evidence and installed third-party skills). They cover all our own code.

## Directory Layout

```
src/core/          pure logic, no I/O (network/: genesis, enode, health; firefly/: config, keystore, request bodies, port, errors, outcome, inputs, invoke, register; trex/: deploy plan, claims, onboarding, amounts; paladin/: node config, artifacts, JSON-RPC, bootstrap, registry, Noto requests, privacy checks)
src/adapters/      I/O: Docker, files, JSON-RPC, the FireFly and Paladin clients, deploy, onboarding and Noto runners, the stack CLI, the FireFly CLI (ff_cli.py, `besu-ff`)
scripts/           thin entry points (stack.py) that call into src/adapters
tests/unit/        unit tests, mirror src/
tests/integration/ tests that need Docker and a live stack (marker: integration)
tests/support/     helpers for tests (JSON-RPC, FireFly and Paladin HTTP, polling, deploy)
network-config/    generated genesis, validator keys, static-nodes.json, demo wallets, firefly/ (config and signer keystores), paladin/ (base configs, certificates, Postgres init) (committed, demo only)
paladin-runtime/   the Paladin configs Compose mounts; `up` copies them from network-config/paladin, `deploy` adds the Noto domain, `reset` removes it (not committed)
contracts/paladin/ the vendored Paladin v1.0.0 contract artifacts and the private Noto ABI, with SHA256SUMS (committed)
contracts/         package.json pinning the T-REX and OnchainID artifacts (node_modules is not committed)
docker-compose.yml the Besu network, FireFly, and three Paladin nodes with one Postgres
deployed-addresses.json  addresses written by `deploy` (not committed)
docs/              PRD, architecture, plan, use cases, deliverables, spike results
tasks/             task lists per phase
spike/             Phase 0 evidence (archive, not part of the stack)
perf/              Caliper benchmarks (Phase 5)
```

`perf/` is created by Phase 5.
