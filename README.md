# besu-with-firefly

A local learning project: a 4-validator QBFT Hyperledger Besu network provisioned with **Hyperledger FireFly** (gateway mode) and **Paladin**, an ERC-3643 (T-REX) compliance token deployed through FireFly, a private **Noto** token on Paladin, a small Python CLI client for FireFly, and **Caliper** performance tests.

> **Status: Phase 0 (spike) and Phase 1 (the Besu network) are complete (2026-10-02), see [docs/spike-results.md](docs/spike-results.md) and [docs/plan.md](docs/plan.md).** Phases 2-5 are not started: FireFly, Paladin, T-REX, the CLI and Caliper are planned, and so are the `deploy` command and the items marked *TBD*.

## Who it serves and how they interact

| Actor | Interaction |
|---|---|
| Developer (the only user) | Python CLI → FireFly REST API; FireFly Explorer UI; Paladin API; Caliper reports |
| Admin (demo identity) | Registers identities, issues claims, mints (Token Agent + Trusted Issuer) |
| Anson, Beatrice (demo identities) | Transfer `COIN`; hold private Noto tokens |

No real users, no real personal data, no authentication. Everything is bound to localhost.

## Key capabilities

- 4-validator QBFT Besu network with `f=1` fault tolerance and 2 RPC nodes, zero-gas
- Genesis generated with `besu operator generate-blockchain-config`; FireFly attached to the external Besu nodes
- Official ERC-3643 T-REX suite (with OnchainID) deployed through FireFly's contract deploy API, exposed via a FireFly contract interface and API
- Compliant transfers: register → claim → mint → transfer, with an on-chain compliance rejection for unverified recipients
- Paladin **Noto** private token: Admin mints to Anson, Anson transfers to Beatrice, a third party cannot see it
- Python CLI client over the FireFly API
- Caliper benchmarks: chain layer (direct RPC) vs FireFly layer, to measure gateway overhead

## Architecture at a glance

All services run in one Docker Compose stack.

| Service | Role | Port |
|---|---|---|
| `besu-validator-1..4` | QBFT validators | none published |
| `besu-rpc-anson` | RPC node | 8545 (HTTP), 8546 (WS) |
| `besu-rpc-beatrice` | RPC node | 8555 (HTTP), 8556 (WS) |
| FireFly core + evmconnect + signer | Gateway mode, single node, keys: admin / anson / beatrice | *TBD* (FireFly default 5000) |
| FireFly Postgres | FireFly state | internal |
| Paladin node1 (notary, registry admin), node2 (Anson), node3 (Beatrice) | Noto private token (`lfdecentralizedtrust/paladin:v1.0.0`), gRPC with mTLS between nodes | RPC 8548, 8648, 8748 (spike values) |
| Paladin Postgres | One server, one database per Paladin node. Paladin must use Postgres: SQLite stalled under multi-node load in the spike | internal |

Caliper 0.6.0 (`perf/`, Node.js) and the Python CLI run on the host. Caliper 0.7.1 dropped the Ethereum connector, so 0.6.0 is used.

## Prerequisites

- Docker Desktop with Docker Compose v2
- Python 3.11+ (CLI, tests)
- Node.js 24 (Caliper 0.6.0, contract tooling). Caliper needs `npm install --no-save web3@1.3.0` by hand because `caliper bind` fails on Windows
- *(optional)* FireFly CLI `ff`, only as a reference for generating config (no Windows release: `go install github.com/hyperledger-firefly/cli/ff@v1.5.0`). The stack uses its own Compose, not `ff start`.

## Getting started

What works today is the Besu network (Phase 1). The commands run from the repo root.

```bash
git clone <repo> && cd besu-with-firefly
python -m venv .venv                  # then activate: .venv\Scripts\activate (Windows) or source .venv/bin/activate
pip install -e ".[dev]"
python scripts/stack.py up            # 4 validators + 2 RPC nodes; waits until all are healthy
pytest -m integration                 # proves the network (about 5 minutes; it stops and restarts validators)
python scripts/stack.py reset         # removes the containers and volumes; the next `up` starts at block 0
```

The genesis, validator keys, `static-nodes.json` and demo wallets are already committed in `network-config/`, so `up` needs no generation step. `python scripts/stack.py init --force` regenerates them (it needs Docker for Besu's own generator and refuses to overwrite without `--force`).

Planned, not built yet: `python scripts/stack.py deploy` (T-REX through FireFly, onboarding), and FireFly and Paladin joining `up` and `reset`.

## Accessing the application

- Besu RPC: Anson `http://localhost:8545` (WS `8546`), Beatrice `http://localhost:8555` (WS `8556`). Validators publish no ports.
- Quick check: `curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' http://localhost:8545`
- *TBD:* FireFly Explorer and Swagger, and the CLI as `besu-ff <command>` (later phases).

## Key documents

| Document | Purpose |
|---|---|
| [docs/prd.md](docs/prd.md) | Requirements and user stories |
| [docs/architecture.md](docs/architecture.md) | Topology, integration, security |
| [docs/plan.md](docs/plan.md) | Phases, locked decisions, risks |
| [docs/use-cases.md](docs/use-cases.md) | End-to-end flows |
| [docs/deliverables.md](docs/deliverables.md) | Per-phase deliverables and how to try them |

## Development notes

- Python: `ruff check .`, `mypy .`, `pytest`
- `src/core/` is pure logic with no I/O; the FireFly HTTP client is an adapter
- The chain, FireFly DB and Paladin DB are not persistent across a reset (but Paladin's DB must survive a plain restart). `python scripts/stack.py reset` resets all three (today it resets the chain).

## Compliance notes

- **Demo network only.** Validator keys, wallet keys and genesis are committed deliberately. They are throwaway demo credentials with no real value. Never reuse them anywhere else.
- No authentication or authorization anywhere. Do not expose any port beyond localhost.
- No real personal data. Anson, Beatrice and Admin are fictional identities. CASL, PIPEDA, GDPR and PCI do not apply.
- The trimmed or full T-REX setup here is a learning exercise, not audit-grade compliance tooling.
