# besu-with-firefly

A local learning project: a single-validator QBFT Hyperledger Besu network with one RPC node, provisioned with **Hyperledger FireFly** (gateway mode) and **Paladin**, an ERC-3643 (T-REX) compliance token deployed through FireFly, a private **Noto** token on Paladin, a small Python CLI client for FireFly, and **Caliper** performance tests.

> **Status: Phases 0 (spike), 1 (the Besu network), 2 (FireFly and the ERC-3643 `COIN` token), 3 (Paladin and the private Noto token), 4 (the `besu-ff` CLI) 5 (Caliper) and 6 (one `docker compose up` for the whole stack) are built (2026-10-04 and 2026-10-05), see [docs/plan.md](docs/plan.md) and [docs/spike-results.md](docs/spike-results.md).** The Phase 5 numbers and the configuration they were measured under are in [docs/perf-results.md](docs/perf-results.md).

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

- Docker Desktop with Docker Compose v2. **This is all the quick route needs** (see Getting started).
- Python 3.11+ (the `besu-ff` CLI, the step-by-step route and the tests)
- Node.js 24 (the step-by-step route installs the pinned T-REX contract packages with `npm ci` in `contracts/`, and the benchmark uses Caliper 0.6.0 in `perf/`; the quick route builds the contract packages into its own image, so it does not need Node). Caliper needs `npm install --no-save web3@1.3.0` by hand because `caliper bind` fails on Windows
- *(optional)* FireFly CLI `ff`, only as a reference for generating config (no Windows release: `go install github.com/hyperledger-firefly/cli/ff@v1.5.0`). The stack uses its own Compose, not `ff start`.

## Getting started (from a fresh clone)

A one-validator Besu network, FireFly in gateway mode, the ERC-3643 token `COIN`, three Paladin nodes with a private Noto token, the `besu-ff` CLI and a Caliper benchmark. Every command runs from the repo root. Use any shell (the commands are written one per line, so they also work in Windows PowerShell).

There are two routes to the same running stack:

- **The quick route** (next section): one `docker compose up -d`. It needs only Docker.
- **The step-by-step route** (steps 1 to 9): `python scripts/stack.py up`, then `deploy`. It needs Python and Node as well, and it is the route the tests use. Use it when you want to see each stage on its own.

### The quick route: one command

Needs only Docker Desktop (Compose v2) and a clone of this repository.

```bash
docker compose up -d
docker wait deployer
```

The first command starts everything. The second waits for the deploy job to finish and prints `0` when it has succeeded (any other number means it failed; see below).

**What happens**
1. **`paladin-seed`** copies the Paladin base configs into `paladin-runtime/` and exits.
2. The 10 long-running containers start: the Besu validator and RPC node, FireFly (core, connector, signer, database), three Paladin nodes and their database.
3. **`deployer`** waits until FireFly, the RPC node and the Paladin nodes are healthy, then waits until the chain is producing blocks, and then runs `python scripts/stack.py deploy` inside a container. That deploys the contracts through FireFly, onboards Anson and Beatrice, mints 1000 COIN, and sets up Paladin (which restarts the three nodes once). It writes `deployed-addresses.json` next to your clone, exactly as the step-by-step route does, and exits.

**How long.** The first time, Docker also pulls the images and builds the small `deployer` image (about 35 s, it downloads the contract packages). After that, `docker compose up -d` returns in about 45 s (when the deployer has started) and the deploy takes a couple of minutes more: six successful fresh runs took between 2 min 40 s and 5 min in all.

**Watch it**
```bash
docker compose logs -f deployer     # the deploy output, live; Ctrl+C stops watching, not the job
docker compose ps -a                # every container; `deployer` shows `exited (0)` when it is done
```

**When it is done** you have the same stack as steps 4 and 5 below. To use it, jump to step 6 (install `besu-ff` first with `pip install -e ".[dev]"`) or run `python scripts/stack.py noto-demo`.

**If the deployer fails** (`docker wait deployer` prints a number other than `0`): `docker compose logs deployer` shows why. The job only does what is missing, so `docker compose up -d` again finishes an interrupted run.

**Tear down**
```bash
docker compose down -v                # removes the containers, their volumes and the network
```
It does not remove the two folders the deploy left in your clone, `paladin-runtime/` and `deployed-addresses.json`. Delete them as well (or run `python scripts/stack.py reset`, which does all of it), or the next `docker compose up` will think the contracts already exist.

**About the `deployer` and the Docker socket.** Paladin needs its nodes restarted once during the deploy, and a container cannot restart other containers by itself. So the `deployer` is given access to your machine's Docker (it mounts `/var/run/docker.sock`). That means the job can control every container on this machine. It is fine for a local demo and is **not** something to copy into a real deployment: see [docs/production-step-by-step.md](docs/production-step-by-step.md), where a deploy runs from a pipeline with approvals. On Linux and macOS hosts, the files the job writes into your clone are owned by `root`.

### The step-by-step route

### 1. Check the prerequisites

```bash
docker compose version      # Docker Desktop must be running; Compose v2
python --version            # 3.11 or newer
node --version              # 24 (needed for the contract packages in step 3)
```

The stack runs 10 containers (a validator, an RPC node, FireFly with its signer, connector and database, and three Paladin nodes with their database). Measured on a machine given 15.5 GiB, they used about 2 GiB; the first `up` also pulls the images, which takes longer.

### 2. Clone and install the Python tools

```bash
git clone <repo-url> besu-with-firefly
cd besu-with-firefly
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell or cmd)
source .venv/bin/activate     # macOS, Linux or Git Bash: use this line instead
pip install -e ".[dev]"       # installs the `besu-ff` command and the test tools
```

### 3. Install the contract packages

```bash
cd contracts
npm ci                        # the pinned T-REX and OnchainID contract artifacts; nothing is compiled
cd ..
```

### 4. Stand up the network

```bash
python scripts/stack.py up
```

This starts the containers and waits until every one is healthy and the chain is producing blocks (2 to 3 minutes, up to 5; longer the first time). It ends with one line per container, each `running healthy`. The genesis, validator keys, demo wallets and the FireFly and Paladin base configs are committed in `network-config/`, so there is no generation step.

### 5. Deploy the contracts

```bash
python scripts/stack.py deploy
```

About 2 minutes. It deploys the T-REX suite through FireFly, creates the `COIN` token and its contract APIs, onboards the demo investors (Anson and Beatrice, both verified) and mints 1000 COIN to Anson. Then it deploys the Paladin registry and Noto contracts, gives the three Paladin nodes their Noto domain, and registers the nodes. It writes `deployed-addresses.json`. It only does what is missing, so it is safe to run again, and running it again finishes an interrupted run.

### 6. Check that it works

```bash
besu-ff query name --contract coin                                   # Coin
besu-ff query balanceOf --contract coin --input _userAddress=@anson  # 1000000000000000000000 (1000 COIN, 18 decimals)
```

Open the FireFly Explorer at http://localhost:5000/ui (no login: nothing here has authentication, and every port is bound to localhost).

### 7. Run the demos

**Demo A: Anson sends COIN to Beatrice, on the public chain through FireFly (ERC-3643).** Amounts are in base units (18 decimals), so `25000000000000000000` is 25 COIN, and `@anson` means that wallet's address.

```bash
besu-ff invoke transfer --contract coin --as anson --input _to=@beatrice --input _amount=25000000000000000000
```

Expect `sent       transfer as anson`, an operation id, and the new balances (Anson 975, Beatrice 25). Show the operation and its FireFly events with `besu-ff tx <operation-id>`.

The same transfer to Admin, who is not a verified investor, is refused by the contract, and nothing moves:

```bash
besu-ff invoke transfer --contract coin --as anson --input _to=@admin --input _amount=10000000000000000000
```

Expect `error: refused by the contract: Transfer not possible` and `balances unchanged`; the command exits with code 1.

**Demo B: Anson sends a private Noto token to Beatrice, on Paladin.**

```bash
python scripts/stack.py noto-demo
```

It deploys a new Noto token (node1 is the notary), mints 100 to Anson, and has Anson send 40 to Beatrice. The last lines are:

```
balance anson@node2     60
balance beatrice@node3  40
node1 (notary) sees coins [40, 60, 100]
node2 (Anson) sees coins [40, 60, 100]
node3 (Beatrice) sees coins [40]
privacy ok: the third node never saw Anson's 100 or his 60
```

So node3 (Beatrice) sees only her own 40, and the public chain's logs show no amounts or party addresses. It deploys a new token on every run and needs `deploy` first.

### 8. Optional: the tests and the benchmark

```bash
pytest                         # unit tests, no stack needed
pytest -m integration          # against the running stack (about 13 minutes)
```

The benchmark has its own section below. It mints extra COIN, so tear the stack down and bring it back up before running the integration tests afterwards.

### 9. Tear down

```bash
python scripts/stack.py reset
```

This removes all the containers and their volumes (the chain, FireFly's database, Paladin's database), `deployed-addresses.json` and `paladin-runtime/` (it also clears a stack that was started with the quick route), so the next `up` starts again at block 0. It leaves your clone alone: the virtual environment, `node_modules/` and the Docker images stay, so a new `up` and `deploy` is quick. `reset` is also the way to get back to a clean 1000 COIN after demo A or the benchmark.

To pause without losing anything, run `docker compose stop`; `docker compose up -d` (or `python scripts/stack.py up`) starts the containers again with the same chain, balances and Paladin state (checked: Anson's balance and the `noto` domain were still there after a stop and an `up`).

### Notes

The genesis, validator keys, `static-nodes.json`, demo wallets and the FireFly config and signer keystores are already committed in `network-config/`, so `up` needs no generation step. `python scripts/stack.py init --force` regenerates them (it needs Docker for Besu's own generator and refuses to overwrite without `--force`).

`deploy` and `onboard` only do what is missing, so running them again sends nothing, and running `deploy` again finishes an interrupted run. `python scripts/stack.py onboard` repeats just the investor onboarding.

A cold `up` takes 2 to 3 minutes (it waits up to 5) and can take longer on a busy machine. `deploy` takes about 2 minutes with Paladin. `noto-demo` needs `deploy` first and deploys a new token on every run.

The Paladin base configs, certificates and database init script are committed in `network-config/paladin/`. `up` copies the configs to `paladin-runtime/` (gitignored), and `deploy` adds the Noto domain and registry to that copy. `reset` removes the Paladin database volume, `paladin-runtime/` and the Paladin entries of `deployed-addresses.json` together with the chain. A plain `docker restart` of a Paladin container keeps its keys and state, because the database is a volume.

## Benchmark (Caliper)

Chain layer (direct JSON-RPC) against FireFly layer, the same `COIN.transfer`. Needs the stack up and deployed.

```bash
cd perf
npm ci
npm install --no-save web3@1.3.0
cd ..
python scripts/stack.py perf-setup --wallets 10 --coins 100    # 20 verified wallets holding COIN, 10 per layer (2 to 4 minutes)
cd perf
npm run round:chain                                            # about 1 minute; results in perf/results/
npm run round:firefly                                          # about 1 minute
cd ..
```

The results note, with the configuration beside every number, is [docs/perf-results.md](docs/perf-results.md). **The setup mints new COIN, so run `python scripts/stack.py reset` after benchmarking, before the integration tests** (`totalSupply` is 1000 in those tests). Details, the load options and why the layers use separate wallets: [perf/README.md](perf/README.md).

## Accessing the application

### UI links by environment

| Environment | FireFly Explorer (web UI) | FireFly API (Swagger) | Contract API docs (Swagger), token `coin` | Paladin UI |
|---|---|---|---|---|
| **Local demo** (this repository, `docker compose up -d`) | http://localhost:5000/ui | http://localhost:5000/api | http://localhost:5000/api/v1/namespaces/default/apis/coin/api | none (JSON-RPC only, see below) |
| Development | not deployed | | | |
| Pre-production | not deployed | | | |
| Production | not deployed | | | |

The local demo is the only environment that exists today. Its Explorer needs no login (the demo has no authentication and its ports are bound to localhost). The other rows are placeholders: fill them in when those environments exist, and see [docs/production-step-by-step.md](docs/production-step-by-step.md) for what building them involves. A beginner's tour of the Explorer is in [docs/firefly-user-guide.md](docs/firefly-user-guide.md).

### Other endpoints (local demo)

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
| [docs/firefly-user-guide.md](docs/firefly-user-guide.md) | Beginner's guide to FireFly and its Explorer UI, with screenshots |
| [docs/production-step-by-step.md](docs/production-step-by-step.md) | Discussion draft: what it would take to run this for real, step by step |

## Development notes

- Python: `ruff check .`, `mypy .`, `pytest` (unit tests); `pytest -m integration` needs the running stack
- `src/core/` is pure logic with no I/O; the FireFly HTTP client is an adapter
- The chain, FireFly DB and Paladin DB are not persistent across a reset (but Paladin's DB must survive a plain restart). `python scripts/stack.py reset` resets all three.

## License

[MIT](LICENSE), for the code and documents in this repository. The Paladin contract artifacts vendored in `contracts/paladin/` are Apache-2.0 (see its README), and the packages installed by `npm ci` and `pip install` keep their own licenses.

## Compliance notes

- **Demo network only.** Validator keys, wallet keys and genesis are committed deliberately. They are throwaway demo credentials with no real value. Never reuse them anywhere else.
- No authentication or authorization anywhere. Do not expose any port beyond localhost.
- No real personal data. Anson, Beatrice and Admin are fictional identities. CASL, PIPEDA, GDPR and PCI do not apply.
- The trimmed or full T-REX setup here is a learning exercise, not audit-grade compliance tooling.
