# besu-with-firefly

A local learning project: a 4-validator QBFT Hyperledger Besu network provisioned with **Hyperledger FireFly** (gateway mode) and **Paladin**, an ERC-3643 (T-REX) compliance token deployed through FireFly, a private **Noto** token on Paladin, a small Python CLI client for FireFly, and **Caliper** performance tests.

> **Status: Phases 0 (spike), 1 (the Besu network) and 2 (FireFly and the ERC-3643 `COIN` token) are built (2026-10-02), see [docs/plan.md](docs/plan.md) and [docs/spike-results.md](docs/spike-results.md).** Phases 3-5 are not started: Paladin, the Python CLI and Caliper are planned, and so are the items marked *TBD*.

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
| `firefly-core`, `firefly-evmconnect`, `firefly-signer` | Gateway mode, single node, keys: admin / anson / beatrice; reaches the chain through `besu-rpc-anson` | 5000 (API, Swagger, Explorer) |
| `firefly-postgres` | FireFly state | internal |
| Paladin node1 (notary, registry admin), node2 (Anson), node3 (Beatrice) | Noto private token (`lfdecentralizedtrust/paladin:v1.0.0`), gRPC with mTLS between nodes | RPC 8548, 8648, 8748 (spike values) |
| Paladin Postgres | One server, one database per Paladin node. Paladin must use Postgres: SQLite stalled under multi-node load in the spike | internal |

Caliper 0.6.0 (`perf/`, Node.js) and the Python CLI run on the host. Caliper 0.7.1 dropped the Ethereum connector, so 0.6.0 is used.

## Prerequisites

- Docker Desktop with Docker Compose v2
- Python 3.11+ (CLI, tests)
- Node.js 24 (the pinned T-REX contract packages, installed with `npm ci` in `contracts/`; later Caliper 0.6.0). Caliper needs `npm install --no-save web3@1.3.0` by hand because `caliper bind` fails on Windows
- *(optional)* FireFly CLI `ff`, only as a reference for generating config (no Windows release: `go install github.com/hyperledger-firefly/cli/ff@v1.5.0`). The stack uses its own Compose, not `ff start`.

## Getting started

The commands run from the repo root. Phases 1 and 2 are built: a 4-validator Besu network, FireFly in gateway mode, and the ERC-3643 token `COIN`.

```bash
git clone <repo> && cd besu-with-firefly
python -m venv .venv                  # then activate: .venv\Scripts\activate (Windows) or source .venv/bin/activate
pip install -e ".[dev]"
(cd contracts && npm ci)              # the pinned T-REX and OnchainID contract artifacts
python scripts/stack.py up            # 4 validators, 2 RPC nodes, FireFly; waits until all is healthy and the chain moves
python scripts/stack.py deploy        # T-REX through FireFly, the COIN APIs, onboarding of Anson and Beatrice, 1000 COIN minted
pytest -m integration                 # proves it all (about 10 minutes; it stops and restarts validators)
python scripts/stack.py reset         # removes containers, volumes and deployed-addresses.json; the next `up` starts at block 0
```

The genesis, validator keys, `static-nodes.json`, demo wallets and the FireFly config and signer keystores are already committed in `network-config/`, so `up` needs no generation step. `python scripts/stack.py init --force` regenerates them (it needs Docker for Besu's own generator and refuses to overwrite without `--force`).

`deploy` and `onboard` only do what is missing, so running them again sends nothing, and running `deploy` again finishes an interrupted run. `python scripts/stack.py onboard` repeats just the investor onboarding.

A cold `up` takes 2 to 3 minutes (it waits up to 5) and can take longer on a busy machine. Planned, not built yet: Paladin joining `up`, `deploy` and `reset` (Phase 3).

## Accessing the application

- FireFly API and Swagger UI: `http://localhost:5000/api`. The FireFly Explorer: `http://localhost:5000/ui`.
- Generated contract APIs (Swagger UI): `http://localhost:5000/api/v1/namespaces/default/apis/coin/api` for the token and `.../apis/identity-registry/api` for the identity registry. For example, the token name: `curl -s -X POST -H "Content-Type: application/json" --data '{}' http://localhost:5000/api/v1/namespaces/default/apis/coin/query/name`
- Besu RPC: Anson `http://localhost:8545` (WS `8546`), Beatrice `http://localhost:8555` (WS `8556`). Validators publish no ports.
- Contract addresses: `deployed-addresses.json` (created by `deploy`, not committed). Wallet addresses and keys: `network-config/wallets.json` (demo only).
- *TBD:* the CLI as `besu-ff <command>` (Phase 4). Step-by-step examples with `curl` are in [docs/deliverables.md](docs/deliverables.md) §4.

## Key documents

| Document | Purpose |
|---|---|
| [docs/prd.md](docs/prd.md) | Requirements and user stories |
| [docs/architecture.md](docs/architecture.md) | Topology, integration, security |
| [docs/plan.md](docs/plan.md) | Phases, locked decisions, risks |
| [docs/use-cases.md](docs/use-cases.md) | End-to-end flows |
| [docs/deliverables.md](docs/deliverables.md) | Per-phase deliverables and how to try them |

## Development notes

- Python: `ruff check .`, `mypy .`, `pytest` (unit tests); `pytest -m integration` needs the running stack
- `src/core/` is pure logic with no I/O; the FireFly HTTP client is an adapter
- The chain, FireFly DB and Paladin DB are not persistent across a reset (but Paladin's DB must survive a plain restart). `python scripts/stack.py reset` resets all three (today it resets the chain and FireFly).

## Compliance notes

- **Demo network only.** Validator keys, wallet keys and genesis are committed deliberately. They are throwaway demo credentials with no real value. Never reuse them anywhere else.
- No authentication or authorization anywhere. Do not expose any port beyond localhost.
- No real personal data. Anson, Beatrice and Admin are fictional identities. CASL, PIPEDA, GDPR and PCI do not apply.
- The trimmed or full T-REX setup here is a learning exercise, not audit-grade compliance tooling.
