Owner: Howin Ho
Created: 2026-10-01
Status: Draft

Companion docs: [docs/plan.md](plan.md) · [docs/prd.md](prd.md) · [docs/architecture.md](architecture.md) · [docs/use-cases.md](use-cases.md)

This document is the single reference for what is deliverable and verifiable at the end of each project phase, and how to try each deliverable from a cold start.

> **Read this first.** Phases 0, 1 and 2 are built, and their commands were run for real: `python scripts/stack.py init|up|deploy|onboard|reset`, `docker compose`, `curl`, `pytest`, `ruff` and `mypy`. Everything for Phases 3 to 5 (`besu-ff`, `perf/`, the Paladin ports) is still a **planned name** from the PRD, to be checked against the repo when each phase is built. There is no web frontend of our own, so there is no Playwright anywhere in this document; FireFly's own Explorer is at `http://localhost:5000/ui`.

---

## §1 Overview Table

| DL-ID | Phase | Milestone | Type | Deliverable | Status |
|---|---|---|---|---|---|
| DL-0.1 | Phase 0 — Spike | N/A | infra | Throwaway minimal Compose (1 Besu, FireFly, Paladin) | Done |
| DL-0.2 | Phase 0 — Spike | N/A | doc | `docs/spike-results.md` with 4 answered risks | Done |
| DL-1.1 | Phase 1 — Network | M1.1 | infra | Genesis, key and `static-nodes.json` generator | Done |
| DL-1.2 | Phase 1 — Network | M1.2 | infra | 4 QBFT validators in Compose | Done |
| DL-1.3 | Phase 1 — Network | M1.3 | infra | RPC node, zero-gas (originally 2 RPC nodes) | Done |
| DL-1.4 | Phase 1 — Network | M1.3 | test | Network integration tests | Done |
| DL-2.1 | Phase 2 — FireFly + ERC-3643 | N/A | infra | FireFly (gateway mode) in Compose | Done |
| DL-2.2 | Phase 2 — FireFly + ERC-3643 | N/A | feature | T-REX deployed through FireFly as `COIN` | Done |
| DL-2.3 | Phase 2 — FireFly + ERC-3643 | N/A | api | Contract interface and API for `COIN` and IdentityRegistry | Done |
| DL-2.4 | Phase 2 — FireFly + ERC-3643 | N/A | feature | Onboarding and compliant transfer | Done |
| DL-2.5 | Phase 2 — FireFly + ERC-3643 | N/A | feature | On-chain compliance rejection | Done |
| DL-2.6 | Phase 2 — FireFly + ERC-3643 | N/A | test | `python scripts/stack.py reset` repeatability | Done |
| DL-3.1 | Phase 3 — Paladin + Noto | N/A | infra | 3 Paladin nodes (notary, Anson, Beatrice) and Postgres in Compose | Planned |
| DL-3.2 | Phase 3 — Paladin + Noto | N/A | feature | Noto deploy, mint, private transfer | Planned |
| DL-3.3 | Phase 3 — Paladin + Noto | N/A | test | Privacy check and three-store reset | Planned |
| DL-4.1 | Phase 4 — Python CLI | N/A | ui | `src/core/` and CLI with 4 commands | Planned |
| DL-4.2 | Phase 4 — Python CLI | N/A | test | Unit and integration suites, lint and types clean | Planned |
| DL-5.1 | Phase 5 — Caliper | N/A | infra | `perf/` Caliper sub-project and wallet setup | Planned |
| DL-5.2 | Phase 5 — Caliper | N/A | feature | Chain-layer and FireFly-layer rounds | Planned |
| DL-5.3 | Phase 5 — Caliper | N/A | doc | Results note | Planned |

---

## §2 Phase 0 — Spike

**Goal**: The developer can say, with evidence, whether FireFly, Paladin, T-REX and Caliper work on this network, and what the fallback is for each that does not.

**Status**: Done, signed off 2026-10-02. Evidence: `docs/spike-results.md` and `spike/` (see `spike/README.md` to re-run).

**Prerequisites**:
```
- [x] Docker Desktop with Compose v2 running
- [x] Python 3.11+ installed
- [x] Node.js installed (version to be recorded by this phase)
- [x] *(optional)* FireFly CLI `ff`, only as a reference for generating config. There is no Windows release, so build it with `go install github.com/hyperledger-firefly/cli/ff@v1.5.0`. `ff start` is not used.
- [x] Repo cloned, on branch main
```

### DL-0.1 — Throwaway minimal Compose

| Field | Value |
|---|---|
| **Type** | infra |
| **Phase** | Phase 0 — Spike |
| **Milestone** | N/A |
| **Traces to** | US-001, FR-15, plan.md Phase 0 steps 1-3 |
| **Demo surface** | CLI (`docker compose`) |

**What it is**: One Besu node, FireFly and one Paladin node, used only to test the risks. It is deleted or archived after Phase 0.

**How to try it**:
```
1. Start the stack: `docker compose -f spike/docker-compose.yml up -d` (path is a planned name)
2. Check containers: `docker compose -f spike/docker-compose.yml ps` -- all `running`
3. Check Besu: `curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' http://localhost:8545`
   Expect a JSON result with a hex block number that grows on repeat.
4. Check FireFly: `curl -s http://localhost:5000/api/v1/status` (port TBD, FireFly default is 5000)
   Expect a JSON status document.
5. Write through FireFly: `POST http://localhost:5000/api/v1/namespaces/default/contracts/deploy?confirm=true` with `{contract, definition, input, key}`, then a `contracts/invoke` and a `contracts/query`. Expect `"status":"Succeeded"` and the stored value back. Working scripts: `spike/firefly/deploy.mjs`, `invoke.mjs`, `idem.mjs`.
```

**Verification checklist**:
- [x] A FireFly contract invoke ends `succeeded` and the transaction receipt exists on Besu
- [x] Token (the largest T-REX contract) deploys through FireFly's deploy API, size recorded and under 24 576 bytes, or the shortfall documented
- [x] Paladin reports healthy from the hand-written config and a Noto mint completes
- [x] A trivial Caliper round writes a report

**Known limitations at this phase**: single Besu node, not the 4-validator network (built in DL-1.2).

### DL-0.2 — `docs/spike-results.md`

| Field | Value |
|---|---|
| **Type** | doc |
| **Phase** | Phase 0 — Spike |
| **Milestone** | N/A |
| **Traces to** | US-001, plan.md D-15, Open Questions 1-5 and 7 |
| **Demo surface** | File on disk |

**What it is**: One section per risk with a feasible / not feasible verdict, evidence, fallback, and the versions to pin.

**How to try it**:
```
1. Open `docs/spike-results.md`
2. Confirm sections exist for: FireFly on external Besu, T-REX through FireFly, Paladin hand-written config, EVM fork level, Caliper and Node version, FireFly idempotency and status names
3. Confirm D-03, D-08 and D-09 in `docs/plan.md` are updated if a result changed them
```

**Verification checklist**:
- [x] Every risk has a verdict and a fallback
- [x] A pinned-versions list exists (Besu, FireFly, Paladin, Node, Caliper)
- [x] The developer has signed off in the file

**Known limitations at this phase**: none. This is the gate for everything else.

**Phase exit gate summary** (from plan.md):
- [x] All DL-0.x deliverables verified
- [x] `docs/spike-results.md` exists with all four sections answered
- [x] D-03, D-08, D-09 are updated if any result requires it
- [x] Image and tool versions to pin are listed
- [x] The developer has signed off

---

## §3 Phase 1 — Network

**Goal**: The developer can start a 4-validator QBFT network with two RPC nodes, kill a validator, and watch the chain keep going.

**Prerequisites**:
```
- [ ] Phase 0 exit gate passed (DL-0.2 signed off)
- [ ] Docker Desktop running
- [ ] Python 3.11+ installed
- [ ] Pinned Besu image tag from spike-results.md available locally
```

### DL-1.1 — Genesis, key and `static-nodes.json` generator

| Field | Value |
|---|---|
| **Type** | infra |
| **Phase** | Phase 1 — Network |
| **Milestone** | M1.1 |
| **Traces to** | US-002, FR-1, FR-14 |
| **Demo surface** | CLI and files on disk |

**What it is**: A script that wraps `besu operator generate-blockchain-config` and writes the genesis, 4 validator keys, `static-nodes.json` and wallet keys. Keys are committed because this is a demo network (D-10).

**How to try it**:
```
1. Create the environment and install: `python -m venv .venv`, activate it, `pip install -e ".[dev]"`
2. Look at what is committed: `network-config/` already holds a generated set (demo keys, D-10).
   To regenerate it: `python scripts/stack.py init --force` (without `--force` it refuses to overwrite)
3. Open `network-config/genesis.json`
   Expect a `qbft` block with `chainId` 20260916, `blockperiodseconds` 2, `zeroBaseFee` true, and `extraData` encoding 4 addresses.
4. List `network-config/validator-keys/`
   Expect `validator-1` to `validator-4`, each with `key`, `key.pub` and `address.txt`.
5. Open `network-config/static-nodes.json`
   Expect 4 enode URLs on `172.28.0.11` to `.14`.
6. Open `network-config/wallets.json`
   Expect `admin`, `anson` and `beatrice` with an address and a private key each.
7. Validate Compose: `docker compose config -q` -- exits 0
```

**Verification checklist**:
- [x] `genesis.json` has a `qbft` block and 4 validator addresses
- [x] 4 validator keys and the `admin`/`anson`/`beatrice` wallet keys exist
- [x] `docker compose config` exits 0
- [x] Running the generator again (`--force`) yields a consistent, valid set
- [x] `ruff check .` and `mypy .` pass

**Known limitations at this phase**: the files are generated but no node has booted from them yet (DL-1.2).

> **Changed 2026-10-03 (plan D-17).** DL-1.2 to DL-1.4 were first built and verified with 4 validators and 2 RPC nodes (including stopping a validator and checking the chain went on). The network was then reduced to 1 validator and 1 RPC node, so the deliverables below describe what exists now.

### DL-1.2 — QBFT validator

| Field | Value |
|---|---|
| **Type** | infra |
| **Phase** | Phase 1 — Network |
| **Milestone** | M1.2 |
| **Traces to** | US-002, FR-2, UC-02 |
| **Demo surface** | CLI |

**What it is**: `besu-validator-1` in Compose, peered with the RPC node by `static-nodes.json`, producing a block every 2 seconds.

**How to try it**:
```
1. Start the stack: `python scripts/stack.py up` (starts the validator, the RPC node and FireFly and waits until all are healthy and the chain moves)
2. Check status: `docker compose ps` -- `besu-validator-1` `running (healthy)`, not restarting
3. Watch blocks: `docker compose logs --tail 5 besu-validator-1`
   Expect `Produced #N` lines about every 2 seconds. The validator publishes no RPC.
4. Check peering through the RPC node: `curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"admin_peers","params":[],"id":1}' http://localhost:8545`
   Expect one peer whose `id` is the content of `network-config/validator-keys/validator-1/key.pub`. (An RPC node dials its static peers on a 60 s cycle, so it can take up to a minute after a cold start.)
```

**Verification checklist**:
- [x] The validator is healthy, produces blocks, and is listed as a peer by the RPC node
- [x] The validator publishes no ports to the host

**Known limitations at this phase**: one validator tolerates no failure: if it stops, the chain stops (R10, now the normal case, plan D-17).

### DL-1.3 — RPC node

| Field | Value |
|---|---|
| **Type** | infra |
| **Phase** | Phase 1 — Network |
| **Milestone** | M1.3 |
| **Traces to** | US-003, FR-2 |
| **Demo surface** | `curl` |

**What it is**: `besu-rpc-anson` (`:8545`/`:8546`), non-validating, zero-gas. FireFly, and later Paladin, use it as their only chain endpoint.

**How to try it**:
```
1. Start everything: `python scripts/stack.py up`
2. Block height: `curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' http://localhost:8545`
   Run it twice a few seconds apart: the number goes up.
3. Gas price: `--data '{"jsonrpc":"2.0","method":"eth_gasPrice","params":[],"id":1}'`
   Expect `"result":"0x0"`.
4. Validator set: `--data '{"jsonrpc":"2.0","method":"qbft_getValidatorsByBlockNumber","params":["latest"],"id":1}'`
   Expect the single address in `network-config/validator-keys/validator-1/address.txt` and nothing else.
```

**Verification checklist**:
- [x] The RPC node is `running` and healthy and its block height keeps increasing
- [x] `eth_gasPrice` is `0x0`
- [x] The RPC node does not run the validator key and is not in the validator set

**Known limitations at this phase**: a single RPC node, so there is no consistency to compare between nodes.

### DL-1.4 — Network integration tests

| Field | Value |
|---|---|
| **Type** | test |
| **Phase** | Phase 1 — Network |
| **Milestone** | M1.3 |
| **Traces to** | US-002, US-003, US-011 |
| **Demo surface** | automated test |

**What it is**: `pytest` tests that prove the validator produces blocks, the RPC node follows it and gas is zero, against the live network.

**How to try it**:
```
1. Start from nothing: `python scripts/stack.py reset` then `python scripts/stack.py up`
2. Run the network tests: `pytest -m integration -k "network or validators"`
3. Run everything: `pytest -m integration`
```

**Verification checklist**:
- [x] Tests pass against a freshly started network
- [x] `ruff check .` and `mypy .` pass

**Known limitations at this phase**: the `f=1` fault-injection tests and the two-RPC-node consistency test were removed with the move to one validator (plan D-17).

**Phase exit gate summary** (from plan.md):
- [x] All DL-1.x deliverables verified
- [x] The validator is healthy and produces blocks (originally: 4 validators tolerant of 1 failure)
- [x] The RPC node follows it (originally: 2 RPC nodes consistent)
- [x] `pytest -m integration` network tests pass

---

## §4 Phase 2 — FireFly + ERC-3643

**Goal**: The developer can deploy `COIN` through FireFly, onboard identities, transfer, and see the chain refuse a non-compliant transfer.

**Prerequisites**:
```
- [x] Phase 1 exit gate passed
- [ ] Docker Desktop running; Python 3.11+ with `pip install -e ".[dev]"`
- [ ] Node.js 24 and the pinned contract packages: `cd contracts && npm ci`
- [ ] Network and FireFly running: `python scripts/stack.py up`
```

Used by the examples below (bash). Wallet addresses come from `network-config/wallets.json`; 1 COIN is `10^18` base units, so 25 COIN is `25000000000000000000`:
```
ADMIN=$(python -c "import json;print(next(w['address'] for w in json.load(open('network-config/wallets.json'))['wallets'] if w['name']=='admin'))")
ANSON=$(python -c "import json;print(next(w['address'] for w in json.load(open('network-config/wallets.json'))['wallets'] if w['name']=='anson'))")
BEATRICE=$(python -c "import json;print(next(w['address'] for w in json.load(open('network-config/wallets.json'))['wallets'] if w['name']=='beatrice'))")
FF=http://localhost:5000/api/v1/namespaces/default
```

### DL-2.1 — FireFly in Compose

| Field | Value |
|---|---|
| **Type** | infra |
| **Phase** | Phase 2 — FireFly + ERC-3643 |
| **Milestone** | N/A |
| **Traces to** | US-004, FR-3 |
| **Demo surface** | `curl` and FireFly Explorer |

**What it is**: FireFly core, evmconnect, signer and Postgres in gateway mode, with keys `admin`, `anson`, `beatrice`. FireFly reaches the chain through `besu-rpc-anson`; it has no Besu node of its own.

**How to try it**:
```
1. Start: `python scripts/stack.py up`
   It waits until all 6 containers are healthy, FireFly is ready and the RPC node is past block 0.
2. Check containers: `docker compose ps` -- 4 `firefly-*` services `running (healthy)`
3. Status: `curl -s http://localhost:5000/api/v1/status`
   Expect `"namespace":{"name":"default",...}` and `"multiparty":{"enabled":false}`.
4. Open the Explorer in a browser: `http://localhost:5000/ui`
   The Swagger UI for the whole FireFly API is at `http://localhost:5000/api`.
```

**Verification checklist**:
- [x] FireFly status reports ready with no manual steps after `python scripts/stack.py up`
- [x] FireFly reaches the chain through `besu-rpc-*`, not a Besu node of its own (the signer reports our chain id and follows `besu-rpc-anson`)
- [x] Three signing keys available (the signer lists `admin`, `anson`, `beatrice`)

**Known limitations at this phase**: only port `5000` is published; FireFly's admin port stays inside the Docker network. A cold `up` takes 2 to 3 minutes and can take longer on a busy machine (`up` waits up to 5 minutes).

### DL-2.2 — T-REX deployed through FireFly as `COIN`

| Field | Value |
|---|---|
| **Type** | feature |
| **Phase** | Phase 2 — FireFly + ERC-3643 |
| **Milestone** | N/A |
| **Traces to** | US-005, FR-4, UC-04 |
| **Demo surface** | CLI and file on disk |

**What it is**: The official T-REX suite (`@tokenysolutions/t-rex` 4.1.6, with `@onchain-id/solidity` 2.1.0) is deployed with FireFly's deploy API, not a direct RPC signer: 12 contracts, 3 wiring calls, then `TREXFactory.deployTREXSuite` creates `COIN` (`Coin`, 18 decimals) with its identity registry, registry storage, claim topics registry, trusted issuers registry and modular compliance.

**How to try it**:
```
1. Install the pinned packages once: `cd contracts && npm ci && cd ..`
2. Run: `python scripts/stack.py deploy`
   It prints each contract and its address, then registers the APIs, unpauses the token and onboards the investors (DL-2.3 and DL-2.4).
3. Open `deployed-addresses.json` (not committed)
   Expect 18 names (the 12 contracts plus token, identity-registry, identity-registry-storage, claim-topics-registry, trusted-issuers-registry, modular-compliance), every address non-zero.
4. Confirm code on-chain for an address:
   `curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_getCode","params":["ADDRESS","latest"],"id":1}' http://localhost:8545`
   Expect a result longer than `0x`.
5. Read the token name through FireFly:
   `curl -s -X POST -H "Content-Type: application/json" --data '{}' $FF/apis/coin/query/name`
   Expect `{"output":"Coin"}`; the same for `symbol` gives `COIN`.
6. List the deploy operations: `curl -s "$FF/operations?type=blockchain_deploy"` -- one `Succeeded` operation per deployed contract.
```

**Verification checklist**:
- [x] All addresses non-zero and have code (checked by size against the pinned artifacts)
- [x] FireFly shows a deploy operation for each contract
- [x] Token name reads `Coin`/`COIN`
- [x] Contracts are the published artifacts (Solidity 0.8.17, no Shanghai-only opcodes; every size is under the 24,576-byte limit, `TREXFactory` closest at 23,495)

**Known limitations at this phase**: the deploy order differs from what the sources suggest (the TREX authority's version must be added before the factory exists); it is recorded in `docs/spike-results.md`. A second `deploy` sends nothing; after a failed or interrupted run, running `deploy` again finishes the job.

### DL-2.3 — Contract interface and API

| Field | Value |
|---|---|
| **Type** | api |
| **Phase** | Phase 2 — FireFly + ERC-3643 |
| **Milestone** | N/A |
| **Traces to** | US-006, FR-5 |
| **Demo surface** | FireFly Swagger and `curl` |

**What it is**: A FireFly contract interface and generated API for `COIN` (`coin`) and for the IdentityRegistry (`identity-registry`). `deploy` also unpauses the token (a new T-REX token is paused) as Admin, through the `coin` API.

**How to try it**:
```
1. After `python scripts/stack.py deploy`, open the generated Swagger UI for the token:
   `http://localhost:5000/api/v1/namespaces/default/apis/coin/api`
   (the one for the registry is the same with `identity-registry`)
2. A read: `curl -s -X POST -H "Content-Type: application/json" --data "{\"input\":{\"_userAddress\":\"$ADMIN\"}}" $FF/apis/coin/query/balanceOf`
   Expect `{"output":"0"}`.
3. The write that `deploy` made: `curl -s -X POST -H "Content-Type: application/json" --data '{}' $FF/apis/coin/query/paused`
   Expect `{"output":false}` (the token was paused until `deploy` called `unpause` through the API).
```

**Verification checklist**:
- [x] A read and a write both succeed through the generated API
- [x] After `python scripts/stack.py reset && python scripts/stack.py up && python scripts/stack.py deploy`, the APIs exist again (and none survive the reset)

**Known limitations at this phase**: `mint` is not the write checked here (it is refused for an unverified recipient); it is proved in DL-2.4. Calling raw FireFly is verbose; the CLI in Phase 4 wraps it.

### DL-2.4 — Onboarding and compliant transfer

| Field | Value |
|---|---|
| **Type** | feature |
| **Phase** | Phase 2 — FireFly + ERC-3643 |
| **Milestone** | N/A |
| **Traces to** | US-007, US-008, FR-6, UC-05, UC-06 |
| **Demo surface** | script or `pytest` (the CLI arrives in Phase 4) |

**What it is**: Admin gives Anson and Beatrice an OnchainID, registers them in the IdentityRegistry and, as the claim issuer, signs a KYC claim that each adds to their own identity, so both are verified. Admin then mints 1000 `COIN` to Anson, and Anson sends `COIN` to Beatrice with his own key.

**How to try it**:
```
1. Onboarding is part of `python scripts/stack.py deploy`; `python scripts/stack.py onboard` repeats it alone.
2. Check the state (right after a fresh deploy):
   `curl -s -X POST -H "Content-Type: application/json" --data "{\"input\":{\"_userAddress\":\"$ANSON\"}}" $FF/apis/identity-registry/query/isVerified`  -- `true` (the same for `$BEATRICE`; for `$ADMIN` it is `false`)
   `curl -s -X POST -H "Content-Type: application/json" --data "{\"input\":{\"_userAddress\":\"$ANSON\"}}" $FF/apis/coin/query/balanceOf`  -- `1000000000000000000000` (1000 COIN); Beatrice has `0`
3. Transfer 25 COIN from Anson to Beatrice, signed with his key:
   `curl -s -X POST -H "Content-Type: application/json" --data "{\"input\":{\"_to\":\"$BEATRICE\",\"_amount\":\"25000000000000000000\"},\"key\":\"$ANSON\"}" "$FF/apis/coin/invoke/transfer?confirm=true"`
   Expect an operation with `"status":"Succeeded"`.
4. Re-check the balances: Anson `975000000000000000000`, Beatrice `25000000000000000000`.
5. Run onboarding again: `python scripts/stack.py onboard`
   Expect no output and no new FireFly operation.
```

**Verification checklist**:
- [x] Balances change by exactly the transfer amount, the total supply stays 1000 COIN
- [x] Re-running register, claim or mint sends no redundant transaction (`onboard` prints nothing and the operation count does not change)
- [x] `pytest -m integration -k "onboarding or claims or transfer"` passes
- [x] The claim signature is accepted by the ClaimIssuer contract, and one signed by another wallet is rejected

**Known limitations at this phase**: driven by script and `pytest`; the CLI lands in DL-4.1. Amounts are in base units (18 decimals).

### DL-2.5 — On-chain compliance rejection

| Field | Value |
|---|---|
| **Type** | feature |
| **Phase** | Phase 2 — FireFly + ERC-3643 |
| **Milestone** | N/A |
| **Traces to** | US-008, FR-7, UC-07 |
| **Demo surface** | contract API and `pytest` |

**What it is**: A transfer to an unverified recipient reverts, enforced by the token contract.

**How to try it**:
```
1. Confirm Admin is not verified: `isVerified` for `$ADMIN` (as in DL-2.4) returns `{"output":false}`
2. Send 10 COIN from Anson to Admin through the contract API:
   `curl -s -X POST -H "Content-Type: application/json" --data "{\"input\":{\"_to\":\"$ADMIN\",\"_amount\":\"10000000000000000000\"},\"key\":\"$ANSON\"}" "$FF/apis/coin/invoke/transfer?confirm=true"`
   Expect HTTP 500 with `EVM reverted: Error("Transfer not possible")`. Nothing is mined.
3. A few seconds later, look at FireFly's record: `curl -s "$FF/operations?type=blockchain_invoke&limit=5"`
   Expect an operation with `"status":"Failed"` and the same error text (it shows `Initialized` for a moment first).
4. Re-check the balances
   Expect no change.
5. Without FireFly: an `eth_call` of `transfer(admin, 1)` from Anson to the token on `http://localhost:8545` reverts with the same `Error(string)`, while the same call to Beatrice returns `true` (done in `tests/integration/test_compliance.py`).
```

**Verification checklist**:
- [x] The operation fails with the contract's revert reason
- [x] Balances and the total supply are unchanged
- [x] The same revert appears when calling FireFly's API directly, not only through the project's client, and when calling Besu directly
- [x] `pytest -m integration -k compliance` passes

**Known limitations at this phase**: the reason text is T-REX's generic `Transfer not possible`; it does not say that the recipient is unverified.

### DL-2.6 — `python scripts/stack.py reset` repeatability

| Field | Value |
|---|---|
| **Type** | test |
| **Phase** | Phase 2 — FireFly + ERC-3643 |
| **Milestone** | N/A |
| **Traces to** | FR-11, UC-09, risk R6 |
| **Demo surface** | CLI |

**What it is**: Proof that the stack can be torn down and rebuilt to a working `COIN` without manual steps.

**How to try it**:
```
1. Run: `python scripts/stack.py reset && python scripts/stack.py up && python scripts/stack.py deploy`
   `reset` lists what it removed, including `deployed-addresses.json`.
2. Run: `pytest -m integration`
3. Repeat steps 1-2 two more times
```

**Verification checklist**:
- [x] After reset, no container or volume remains, `deployed-addresses.json` is gone, and no contract interface or API is left in FireFly
- [x] An interrupted `deploy` (killed in the middle of the plan) is finished by running `deploy` again, with one token and no duplicate
- [x] Three consecutive runs all pass: see `tasks/todo.md` Task 13 for the runs on the original 4-validator network (gate `integration and not fault_injection`, 63 of 63 three times, the fault-injection tests kept apart) and the repeat on the current network below

**Known limitations at this phase**: Paladin's database is added to `reset` in DL-3.3. On the original 4-validator network the fault-injection tests (stopping a validator) failed about once per full run, because the 3 validators left were exactly the quorum and QBFT's round timer doubles (4, 8, 16, 32, 64 s). That is why the network was reduced to one validator on 2026-10-03 (plan D-17) and those tests were removed; `pytest -m integration` is now the only suite.

**Phase exit gate summary** (from plan.md):
- [x] All DL-2.x deliverables verified
- [x] Integration tests (onboarding, transfer, rejection) pass
- [x] Re-running register or claim sends no redundant transaction
- [x] Reset repeatability proven (on the original network three clean runs of the gate; on the current one-validator network see Task 13 in `tasks/todo.md`)

---

## §5 Phase 3 — Paladin + Noto

**Goal**: The developer can mint a private Noto token to Anson, send it to Beatrice, and show that a non-party cannot see it.

**Prerequisites**:
```
- [ ] Phase 2 exit gate passed
- [ ] Paladin image `lfdecentralizedtrust/paladin:v1.0.0` (or the tag from spike-results.md) pulled
- [ ] Hand-written Paladin config from the spike committed
```

### DL-3.1 — Paladin nodes and Postgres

| Field | Value |
|---|---|
| **Type** | infra |
| **Phase** | Phase 3 — Paladin + Noto |
| **Milestone** | N/A |
| **Traces to** | US-009, FR-8 |
| **Demo surface** | CLI and Paladin API |

**What it is**: Three Paladin nodes (node1 notary and registry admin, node2 Anson, node3 Beatrice) and one Postgres (a database per node) in Compose, connected to `besu-rpc-*` and to each other over gRPC with mTLS. The registry and Noto contracts are deployed and every node is registered in the EVM registry.

**How to try it**:
```
1. Start: `python scripts/stack.py up`
2. `docker compose ps` -- three Paladin containers and Postgres `running`
3. Ask each node its name (ports are the spike values): `curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","id":1,"method":"transport_nodeName","params":[]}' http://localhost:8548` then `:8648` and `:8748`
   Expect `node1`, `node2`, `node3`.
4. List the registered nodes on node1: same call with `"method":"reg_queryEntries","params":["evm-registry",{"limit":20},"any"]`
   Expect entries for `node1`, `node2` and `node3`.
5. `docker logs paladin-node1 | grep "TLS handshake completed"`
   Expect handshakes with node2 and node3 after the first Noto call.
```

**Verification checklist**:
- [ ] All Paladin containers and Postgres healthy
- [ ] Each node reaches its Besu RPC node
- [ ] All three nodes appear in the EVM registry
- [ ] `domain_listDomains` returns `noto` on every node

**Known limitations at this phase**: the Paladin config is hand-written and may differ from the operator's output. Paladin must use Postgres and its DB must be a volume, because key addresses depend on the path index mapping stored there.

### DL-3.2 — Noto deploy, mint, private transfer

| Field | Value |
|---|---|
| **Type** | feature |
| **Phase** | Phase 3 — Paladin + Noto |
| **Milestone** | N/A |
| **Traces to** | US-009, FR-8, UC-08 |
| **Demo surface** | script against the Paladin API |

**What it is**: A Noto token deployed with node1 as notary; node1 mints to Anson on node2; Anson transfers to Beatrice on node3.

**How to try it**:
```
1. Run the Noto script (`scripts/noto_demo.py`, planned name; the spike equivalent is `spike/paladin/noto-3node.mjs`): deploy the token, mint 100 to `anson@node2`, transfer 40 to `beatrice@node3`
2. Query Beatrice's node: `ptx_call` `balanceOf` for `beatrice@node3`
   Expect `totalBalance` 40.
3. Query Anson's node for `anson@node2`
   Expect `totalBalance` 60.
```

**Verification checklist**:
- [ ] Mint and transfer complete
- [ ] Beatrice's balance equals the amount sent

**Known limitations at this phase**: not driven by the CLI (FR-18, post-MVP).

### DL-3.3 — Privacy check and three-store reset

| Field | Value |
|---|---|
| **Type** | test |
| **Phase** | Phase 3 — Paladin + Noto |
| **Milestone** | N/A |
| **Traces to** | US-009, FR-11, UC-08, UC-09, risk R6 and R11 |
| **Demo surface** | `pytest` and Besu RPC |

**What it is**: Evidence that a non-party sees nothing, plus `python scripts/stack.py reset` now clearing the chain, FireFly DB and Paladin DB together.

**How to try it**:
```
1. Run: `pytest -m integration -k noto`
2. List the coin amounts each node can see (spike equivalent: `spike/paladin/coins-by-node.mjs TOKEN`)
   Expect node1 and node2 to list 40, 60 and 100, and node3 to list 40 only.
   Inspect the token's logs on Besu with `eth_getLogs`
   Expect no plain 100, 40 or 60 in the log data.
3. Run: `python scripts/stack.py reset && python scripts/stack.py up`
4. Query Paladin
   Expect a clean state with no Noto token from before the reset.
```

**Verification checklist**:
- [ ] A Paladin node that is not a party does not see the transfer
- [ ] The public chain data shows no amounts or parties
- [ ] After reset, Paladin starts clean against the fresh chain

**Known limitations at this phase**: all nodes share one host, so this shows the protocol, not real isolation (R11).

**Phase exit gate summary** (from plan.md):
- [ ] All DL-3.x deliverables verified
- [ ] Noto integration tests pass
- [ ] `python scripts/stack.py reset` clears all three stores

---

## §6 Phase 4 — Python CLI

**Goal**: The developer can drive FireFly from a small CLI instead of raw API calls.

**Prerequisites**:
```
- [ ] Phase 3 exit gate passed
- [ ] Stack up and deployed: `python scripts/stack.py up && python scripts/stack.py deploy`
- [ ] Python 3.11+ with project dependencies installed
```

### DL-4.1 — `src/core/` and the CLI

| Field | Value |
|---|---|
| **Type** | ui |
| **Phase** | Phase 4 — Python CLI |
| **Milestone** | N/A |
| **Traces to** | US-010, FR-9, FR-10, UC-05, UC-06, UC-11 |
| **Demo surface** | CLI |

**What it is**: Pure logic in `src/core/` with a port, a FireFly HTTP adapter and a CLI adapter offering register, invoke, query, and show tx/events.

**How to try it** (command names are planned):
```
1. `besu-ff query balanceOf --contract coin --address ANSON_ADDRESS`
   Expect a number.
2. `besu-ff invoke transfer --contract coin --as anson --to BEATRICE_ADDRESS --amount 25`
   Expect a transfer-sent message with the operation id, then updated balances.
3. `besu-ff invoke transfer --contract coin --as anson --to ADMIN_ADDRESS --amount 10`
   Expect a compliance error with the revert reason, exit code non-zero.
4. `besu-ff tx OPERATION_ID`
   Expect the operation status and any events.
```

**Verification checklist**:
- [ ] Each command maps to one FireFly API call
- [ ] The CLI never prints success for a pending or unknown operation
- [ ] `src/core/` has no `print`, `input` or network call
- [ ] `ruff check .` and `mypy .` pass

**Known limitations at this phase**: no Paladin commands (FR-18, post-MVP).

### DL-4.2 — Unit and integration suites

| Field | Value |
|---|---|
| **Type** | test |
| **Phase** | Phase 4 — Python CLI |
| **Milestone** | N/A |
| **Traces to** | US-010, US-011, FR-12 |
| **Demo surface** | automated test |

**What it is**: Unit tests with a mocked port, and integration tests against the live stack.

**How to try it**:
```
1. `ruff check .` -- no findings
2. `mypy .` -- no issues
3. `pytest` -- unit tests pass without a running stack
4. `python scripts/stack.py reset && python scripts/stack.py up && python scripts/stack.py deploy && pytest -m integration` -- repeat 3 times
```

**Verification checklist**:
- [ ] All unit tests pass offline
- [ ] Integration tests pass in 3 consecutive fresh-stack runs
- [ ] No test is marked flaky or skipped without a reason

**Known limitations at this phase**: none.

**Phase exit gate summary** (from plan.md):
- [ ] All DL-4.x deliverables verified
- [ ] `ruff check .`, `mypy .`, `pytest` all pass
- [ ] Integration tests pass across 3 consecutive fresh-stack runs

---

## §7 Phase 5 — Caliper

**Goal**: The developer can see throughput and latency for the chain and for FireFly, and the difference between them.

**Prerequisites**:
```
- [ ] Phase 4 exit gate passed
- [ ] Node version and Caliper version from spike-results.md installed
- [ ] Stack up and deployed
```

### DL-5.1 — `perf/` and wallet setup

| Field | Value |
|---|---|
| **Type** | infra |
| **Phase** | Phase 5 — Caliper |
| **Milestone** | N/A |
| **Traces to** | US-012, FR-13 |
| **Demo surface** | CLI |

**What it is**: A separate Node sub-project with Caliper config for `besu-rpc-*` and a setup step that creates N verified wallets holding `COIN`.

**How to try it**:
```
1. `cd perf && npm install && npm install --no-save web3@1.3.0` (planned layout; Caliper 0.6.0, because `caliper bind` does not work on Windows)
2. Run the wallet setup with N=20 (flag or env name per `perf/README`)
3. Spot-check a wallet: `isVerified` and `balanceOf` through the contract API
   Expect verified and a non-zero balance.
```

**Verification checklist**:
- [ ] N wallets verified on-chain, N configurable
- [ ] Setup duration recorded

**Known limitations at this phase**: setup can take longer than the rounds (R7).

### DL-5.2 — Chain-layer and FireFly-layer rounds

| Field | Value |
|---|---|
| **Type** | feature |
| **Phase** | Phase 5 — Caliper |
| **Milestone** | N/A |
| **Traces to** | US-012, FR-13, UC-10 |
| **Demo surface** | Caliper report |

**What it is**: The same `Token.transfer` sent directly over JSON-RPC and through FireFly's contract API.

**How to try it**:
```
1. Run the chain-layer round (command per `perf/README`)
   Expect a report with TPS and latency.
2. Run the FireFly-layer round
   Expect a second report.
3. Repeat both from a fresh `python scripts/stack.py reset && python scripts/stack.py up && python scripts/stack.py deploy`
```

**Verification checklist**:
- [ ] Both reports exist
- [ ] The two runs are reproducible from a fresh stack

**Known limitations at this phase**: Caliper has no FireFly connector, so the FireFly round uses a small custom Caliper connector (proven in Phase 0). Caliper 0.7.1 has no Ethereum connector, so 0.6.0 is used.

### DL-5.3 — Results note

| Field | Value |
|---|---|
| **Type** | doc |
| **Phase** | Phase 5 — Caliper |
| **Milestone** | N/A |
| **Traces to** | US-012, plan.md anti-gate, risk R13 |
| **Demo surface** | File on disk |

**What it is**: A short note with both result sets, the difference, the genesis settings (block period, gas limit), and the caveat that results describe this demo configuration.

**How to try it**:
```
1. Open the results note (`docs/perf-results.md`, planned name)
2. Confirm it lists chain-layer and FireFly-layer TPS and latency, the difference, and the genesis settings
```

**Verification checklist**:
- [ ] Numbers are never published without the configuration
- [ ] The caveat about Besu limits is present

**Known limitations at this phase**: no tuning for maximum throughput.

**Phase exit gate summary** (from plan.md):
- [ ] All DL-5.x deliverables verified
- [ ] Both rounds reproducible from a fresh `python scripts/stack.py reset && python scripts/stack.py up && python scripts/stack.py deploy`
- [ ] Results note committed

---

## §8 How to Run a Full End-to-End Demo

Run this after Phase 4 (Phase 5 is optional for the demo).

**1. Start the stack**
```bash
python scripts/stack.py reset
python scripts/stack.py up
python scripts/stack.py deploy
docker compose ps
```
All containers should be `running`. (The stack script is a planned name.)

**2. Walk through the primary flow**
- Show the network: DL-1.2 and DL-1.3 (kill a validator, watch the chain continue).
- Show the deploy: DL-2.2 and DL-2.3 (everything went through FireFly, check the Explorer).
- Onboard and transfer: DL-2.4, using the CLI from DL-4.1.
- Show the rejection: DL-2.5, same transfer to Admin fails with a revert reason.
- Show the private token: DL-3.2 and DL-3.3 (Beatrice sees it, a non-party does not).
- Optional: DL-5.2 and DL-5.3 for the numbers.

**3. Show the key outputs**
- `curl` against `:8545` shows increasing blocks and a `0x0` gas price
- `deployed-addresses.json` with non-zero addresses
- CLI output with balances and the compliance error
- FireFly Explorer showing the deploy and transfer operations
- Caliper reports and the results note

**4. Tear down**
```bash
docker compose down -v
```
(or `python scripts/stack.py reset`, which clears the chain, FireFly DB and Paladin DB together). Everything resets to genesis.
