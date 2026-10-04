# besu-with-firefly

A local learning project: a single-validator QBFT Hyperledger Besu network with one RPC node, provisioned with **Hyperledger FireFly** (gateway mode) and **Paladin**, an ERC-3643 (T-REX) compliance token deployed through FireFly, a private **Noto** token on Paladin, a small Python CLI client for FireFly, and **Caliper** performance tests.

> **Status: Phases 0 (spike), 1 (the Besu network), 2 (FireFly and the ERC-3643 `COIN` token), 3 (Paladin and the private Noto token), 4 (the `besu-ff` CLI) and 5 (Caliper) are built (2026-10-04), see [docs/plan.md](docs/plan.md) and [docs/spike-results.md](docs/spike-results.md).** The Phase 5 numbers and the configuration they were measured under are in [docs/perf-results.md](docs/perf-results.md).

## Who it serves and how they interact

| Actor | Interaction |
|---|---|
| Developer (the only user) | Python CLI → FireFly REST API; FireFly Explorer UI; Paladin API; Caliper reports |
| Admin (demo identity) | Registers identities, issues claims, mints (Token Agent + Trusted Issuer) |
| Anson, Beatrice (demo identities) | Transfer `COIN`; hold private Noto tokens |

No real users, no real personal data, no authentication. Everything is bound to localhost.

## Key capabilities

- QBFT Besu network with one validator and one RPC node, zero-gas (it was 4 validators and 2 RPC nodes until 2026-10-03; one validator tolerates no failure, but runs on a laptop without the consensus pauses of a bare quorum)
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
| `besu-validator-1` | QBFT validator | none published |
| `besu-rpc-anson` | RPC node (the only one, used by everything) | 8545 (HTTP), 8546 (WS) |
| `firefly-core`, `firefly-evmconnect`, `firefly-signer` | Gateway mode, single node, keys: admin / anson / beatrice; reaches the chain through `besu-rpc-anson` | 5000 (API, Swagger, Explorer) |
| `firefly-postgres` | FireFly state | internal |
| Paladin node1 (notary, registry admin), node2 (Anson), node3 (Beatrice) | Noto private token (`lfdecentralizedtrust/paladin:v1.0.0`), gRPC with mTLS between nodes | RPC 8548, 8648, 8748 (spike values) |
| Paladin Postgres | One server, one database per Paladin node. Paladin must use Postgres: SQLite stalled under multi-node load in the spike | internal |

Caliper 0.6.0 (`perf/`, Node.js) and the Python CLI run on the host. Caliper 0.7.1 dropped the Ethereum connector, so 0.6.0 is used.

## Prerequisites

- Docker Desktop with Docker Compose v2
- Python 3.11+ (CLI, tests)
- Node.js 24 (the pinned T-REX contract packages, installed with `npm ci` in `contracts/`, and Caliper 0.6.0 in `perf/`). Caliper needs `npm install --no-save web3@1.3.0` by hand because `caliper bind` fails on Windows
- *(optional)* FireFly CLI `ff`, only as a reference for generating config (no Windows release: `go install github.com/hyperledger-firefly/cli/ff@v1.5.0`). The stack uses its own Compose, not `ff start`.

## Getting started

The commands run from the repo root. A one-validator Besu network, FireFly in gateway mode, the ERC-3643 token `COIN`, three Paladin nodes with a private Noto token, the `besu-ff` CLI and a Caliper benchmark are built.

```bash
git clone <repo> && cd besu-with-firefly
python -m venv .venv                  # then activate: .venv\Scripts\activate (Windows) or source .venv/bin/activate
pip install -e ".[dev]"
(cd contracts && npm ci)              # the pinned T-REX and OnchainID contract artifacts
python scripts/stack.py up            # 1 validator, 1 RPC node, FireFly, 3 Paladin nodes; waits until all is healthy and the chain moves
python scripts/stack.py deploy        # T-REX through FireFly, the COIN APIs, onboarding of Anson and Beatrice, 1000 COIN minted;
                                      # then the Paladin contracts, the Noto domain and the node registry (about 2 minutes)
python scripts/stack.py noto-demo     # a new Noto token: mint 100 to Anson, he sends 40 to Beatrice, what each node sees
pytest -m integration                 # proves it all (about 13 minutes)
python scripts/stack.py reset         # removes containers, volumes and deployed-addresses.json; the next `up` starts at block 0
```

The genesis, validator keys, `static-nodes.json`, demo wallets and the FireFly config and signer keystores are already committed in `network-config/`, so `up` needs no generation step. `python scripts/stack.py init --force` regenerates them (it needs Docker for Besu's own generator and refuses to overwrite without `--force`).

`deploy` and `onboard` only do what is missing, so running them again sends nothing, and running `deploy` again finishes an interrupted run. `python scripts/stack.py onboard` repeats just the investor onboarding.

## Benchmark (Caliper)

Chain layer (direct JSON-RPC) against FireFly layer, the same `COIN.transfer`. Needs the stack up and deployed.

```bash
cd perf && npm ci && npm install --no-save web3@1.3.0 && cd ..
python scripts/stack.py perf-setup --wallets 10 --coins 100    # 20 verified wallets holding COIN, 10 per layer (2 to 4 minutes)
(cd perf && npm run round:chain && npm run round:firefly)       # about 1 minute each; results in perf/results/
```

The results note, with the configuration beside every number, is [docs/perf-results.md](docs/perf-results.md). **The setup mints new COIN, so run `python scripts/stack.py reset` after benchmarking, before the integration tests** (`totalSupply` is 1000 in those tests). Details, the load options and why the layers use separate wallets: [perf/README.md](perf/README.md).

A cold `up` takes 2 to 3 minutes (it waits up to 5) and can take longer on a busy machine. `deploy` takes about 2 minutes with Paladin. `noto-demo` needs `deploy` first and deploys a new token on every run.

The Paladin base configs, certificates and database init script are committed in `network-config/paladin/`. `up` copies the configs to `paladin-runtime/` (gitignored), and `deploy` adds the Noto domain and registry to that copy. `reset` removes the Paladin database volume, `paladin-runtime/` and the Paladin entries of `deployed-addresses.json` together with the chain. A plain `docker restart` of a Paladin container keeps its keys and state, because the database is a volume.

## Accessing the application

- FireFly API and Swagger UI: `http://localhost:5000/api`. The FireFly Explorer: `http://localhost:5000/ui`.
- Generated contract APIs (Swagger UI): `http://localhost:5000/api/v1/namespaces/default/apis/coin/api` for the token and `.../apis/identity-registry/api` for the identity registry. For example, the token name: `curl -s -X POST -H "Content-Type: application/json" --data '{}' http://localhost:5000/api/v1/namespaces/default/apis/coin/query/name`
- Besu RPC: `http://localhost:8545` (WS `8546`). The validator publishes no ports.
- Paladin JSON-RPC: `http://localhost:8548` (node1, notary), `:8648` (node2, Anson), `:8748` (node3, Beatrice). For example: `curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","id":1,"method":"transport_nodeName","params":[]}' http://localhost:8548`
- Contract addresses: `deployed-addresses.json` (created by `deploy`, not committed). Wallet addresses and keys: `network-config/wallets.json` (demo only).
- The CLI, `besu-ff <command>` (installed by `pip install -e ".[dev]"`; the stack must be up and deployed). `--json` and `--network-dir` go before the command; `@anson` in a value is that wallet's address; amounts are in base units (18 decimals):
  ```
  besu-ff query balanceOf --contract coin --input _userAddress=@anson
  besu-ff invoke transfer --contract coin --as anson --input _to=@beatrice --input _amount=25000000000000000000
  besu-ff tx OPERATION_ID                       # the operation, its transaction and FireFly's events
  besu-ff register --name coin-copy --abi abi.json --address 0x...   # a contract interface and API
  ```
  Exit codes: `0` done, `1` failed or refused by the contract, `3` pending or unknown (never reported as done; check with `tx`), `2` bad usage. Examples with `curl` are in [docs/deliverables.md](docs/deliverables.md) §4.

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
- The chain, FireFly DB and Paladin DB are not persistent across a reset (but Paladin's DB must survive a plain restart). `python scripts/stack.py reset` resets all three.

## Compliance notes

- **Demo network only.** Validator keys, wallet keys and genesis are committed deliberately. They are throwaway demo credentials with no real value. Never reuse them anywhere else.
- No authentication or authorization anywhere. Do not expose any port beyond localhost.
- No real personal data. Anson, Beatrice and Admin are fictional identities. CASL, PIPEDA, GDPR and PCI do not apply.
- The trimmed or full T-REX setup here is a learning exercise, not audit-grade compliance tooling.
