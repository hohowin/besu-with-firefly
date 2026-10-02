# besu-with-firefly

A local learning project: a 4-validator QBFT Hyperledger Besu network provisioned with **Hyperledger FireFly** (gateway mode) and **Paladin**, an ERC-3643 (T-REX) compliance token deployed through FireFly, a private **Noto** token on Paladin, a small Python CLI client for FireFly, and **Caliper** performance tests.

> **Status: Phase 0 (spike) is complete and signed off (2026-10-02), see [docs/spike-results.md](docs/spike-results.md).** Phases 1-5 are not started, so the commands below are planned names. Items marked *TBD* are filled in as each phase is built. See [docs/plan.md](docs/plan.md).

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

*TBD — filled in after Phase 1–2.* Planned shape:

```bash
git clone <repo> && cd besu-with-firefly
python scripts/stack.py up        # Besu network + FireFly + Paladin
python scripts/stack.py deploy    # deploy T-REX via FireFly, register interface/API, onboard Admin/Anson/Beatrice
python scripts/stack.py reset     # docker compose down -v; resets chain, FireFly DB and Paladin DB together
```

## Accessing the application

*TBD.* Planned: FireFly Explorer and Swagger on the FireFly port, Besu RPC on `localhost:8545` / `localhost:8555`, and the CLI as `besu-ff <command>`.

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
- The chain, FireFly DB and Paladin DB are not persistent across a reset (but Paladin's DB must survive a plain restart). `python scripts/stack.py reset` resets all three.
- The `_knowledge/` folder is reference material from an earlier project and is deleted when this project is complete

## Compliance notes

- **Demo network only.** Validator keys, wallet keys and genesis are committed deliberately. They are throwaway demo credentials with no real value. Never reuse them anywhere else.
- No authentication or authorization anywhere. Do not expose any port beyond localhost.
- No real personal data. Anson, Beatrice and Admin are fictional identities. CASL, PIPEDA, GDPR and PCI do not apply.
- The trimmed or full T-REX setup here is a learning exercise, not audit-grade compliance tooling.
