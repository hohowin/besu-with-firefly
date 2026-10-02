Owner: Howin Ho
Created: 2026-10-01
Status: Draft

Companion docs: [docs/plan.md](plan.md) · [docs/prd.md](prd.md) · [docs/architecture.md](architecture.md) · [docs/use-cases.md](use-cases.md)

This document is the single reference for what is deliverable and verifiable at the end of each project phase, and how to try each deliverable from a cold start.

> **Read this first.** Nothing is built yet. Commands that call Docker, `curl`, `pytest`, `ruff` and `mypy` are real. The `make` targets, script names, file paths and CLI command names (`make up`, `make deploy`, `make reset`, `besu-ff`, `network/generate.py`, `perf/`) are **planned names** from the PRD. Check them against the repo when each phase is built. Ports other than Besu's `8545/8546` and `8555/8556` are TBD until Phase 0 (FireFly's default is `5000`). There is no web frontend, so there is no Playwright anywhere in this document.

---

## §1 Overview Table

| DL-ID | Phase | Milestone | Type | Deliverable | Status |
|---|---|---|---|---|---|
| DL-0.1 | Phase 0 — Spike | N/A | infra | Throwaway minimal Compose (1 Besu, FireFly, Paladin) | Planned |
| DL-0.2 | Phase 0 — Spike | N/A | doc | `docs/spike-results.md` with 4 answered risks | Planned |
| DL-1.1 | Phase 1 — Network | M1.1 | infra | Genesis, key and `static-nodes.json` generator | Planned |
| DL-1.2 | Phase 1 — Network | M1.2 | infra | 4 QBFT validators in Compose | Planned |
| DL-1.3 | Phase 1 — Network | M1.3 | infra | 2 RPC nodes, zero-gas, consistent | Planned |
| DL-1.4 | Phase 1 — Network | M1.3 | test | Network integration tests | Planned |
| DL-2.1 | Phase 2 — FireFly + ERC-3643 | N/A | infra | FireFly (gateway mode) in Compose | Planned |
| DL-2.2 | Phase 2 — FireFly + ERC-3643 | N/A | feature | T-REX deployed through FireFly as `COIN` | Planned |
| DL-2.3 | Phase 2 — FireFly + ERC-3643 | N/A | api | Contract interface and API for `COIN` and IdentityRegistry | Planned |
| DL-2.4 | Phase 2 — FireFly + ERC-3643 | N/A | feature | Onboarding and compliant transfer | Planned |
| DL-2.5 | Phase 2 — FireFly + ERC-3643 | N/A | feature | On-chain compliance rejection | Planned |
| DL-2.6 | Phase 2 — FireFly + ERC-3643 | N/A | test | `make reset` repeatability | Planned |
| DL-3.1 | Phase 3 — Paladin + Noto | N/A | infra | 2 Paladin nodes, notary, DB in Compose | Planned |
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

**Prerequisites**:
```
- [ ] Docker Desktop with Compose v2 running
- [ ] Python 3.11+ installed
- [ ] Node.js installed (version to be recorded by this phase)
- [ ] FireFly CLI `ff` installed (version to be recorded)
- [ ] Repo cloned, on branch main
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
5. Attach and write: with `ff init ethereum` using `--blockchain-node besu --remote-node-url http://HOST:8545`, send one contract invoke and read the operation status.
```

**Verification checklist**:
- [ ] A FireFly contract invoke ends `succeeded` and the transaction receipt exists on Besu
- [ ] Token (the largest T-REX contract) deploys through FireFly's deploy API, size recorded and under 24 576 bytes, or the shortfall documented
- [ ] Paladin reports healthy from the hand-written config and a Noto mint completes
- [ ] A trivial Caliper round writes a report

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
- [ ] Every risk has a verdict and a fallback
- [ ] A pinned-versions list exists (Besu, FireFly, Paladin, Node, Caliper)
- [ ] The developer has signed off in the file

**Known limitations at this phase**: none. This is the gate for everything else.

**Phase exit gate summary** (from plan.md):
- [ ] All DL-0.x deliverables verified
- [ ] `docs/spike-results.md` exists with all four sections answered
- [ ] D-03, D-08, D-09 are updated if any result requires it
- [ ] Image and tool versions to pin are listed
- [ ] The developer has signed off

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
1. Run the generator: `python network/generate.py` (planned name)
2. Open `network-config/genesis.json`
   Expect a `qbft` block with `chainId` 20260916, `blockperiodseconds` 2, and `extraData` encoding 4 addresses.
3. List `network-config/validator-keys/`
   Expect 4 key folders.
4. Open `network-config/static-nodes.json`
   Expect 4 enode URLs.
5. Validate Compose: `docker compose config` -- exits 0
```

**Verification checklist**:
- [ ] `genesis.json` has a `qbft` block and 4 validator addresses
- [ ] 4 validator keys and the `admin`/`anson`/`beatrice` wallet keys exist
- [ ] `docker compose config` exits 0
- [ ] Running the generator again yields a consistent, valid set
- [ ] `ruff check .` and `mypy .` pass if the generator is Python

**Known limitations at this phase**: the files are generated but no node has booted from them yet (DL-1.2).

### DL-1.2 — 4 QBFT validators

| Field | Value |
|---|---|
| **Type** | infra |
| **Phase** | Phase 1 — Network |
| **Milestone** | M1.2 |
| **Traces to** | US-002, FR-2, UC-02, UC-03 |
| **Demo surface** | CLI |

**What it is**: `besu-validator-1..4` in Compose, peered by `static-nodes.json`, producing a block every 2 seconds.

**How to try it**:
```
1. Start validators: `docker compose up -d besu-validator-1 besu-validator-2 besu-validator-3 besu-validator-4`
2. Check status: `docker compose ps` -- all 4 `running`, none restarting
3. Check peers: `docker compose logs besu-validator-1 | grep -i peer`
   Expect peer count of at least 3.
4. Stop one: `docker stop besu-validator-4`
5. Watch height (needs an RPC node, see DL-1.3, or a validator RPC if enabled): repeat `eth_blockNumber` for 30 seconds
   Expect the number to keep increasing.
6. Restart: `docker start besu-validator-4` -- it rejoins
```

**Verification checklist**:
- [ ] All 4 validators healthy, peer count at least 3
- [ ] Block height increases within 30 seconds of stopping one validator
- [ ] The stopped validator rejoins cleanly

**Known limitations at this phase**: stopping 2 validators halts the chain (R10, accepted).

### DL-1.3 — 2 RPC nodes

| Field | Value |
|---|---|
| **Type** | infra |
| **Phase** | Phase 1 — Network |
| **Milestone** | M1.3 |
| **Traces to** | US-003, FR-2 |
| **Demo surface** | `curl` |

**What it is**: `besu-rpc-anson` (`:8545`/`:8546`) and `besu-rpc-beatrice` (`:8555`/`:8556`), non-validating, zero-gas.

**How to try it**:
```
1. Start everything: `docker compose up -d`
2. Query Anson: `curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' http://localhost:8545`
3. Wait 5 seconds and query Beatrice: same command against `http://localhost:8555`
   Expect block numbers within 1 of each other.
4. Gas price on both: `--data '{"jsonrpc":"2.0","method":"eth_gasPrice","params":[],"id":1}'`
   Expect `"result":"0x0"` on both.
```

**Verification checklist**:
- [ ] Both RPC nodes `running`
- [ ] Block numbers agree within 1 block
- [ ] `eth_gasPrice` is `0x0` on both
- [ ] Neither RPC node starts with a validator key

**Known limitations at this phase**: no FireFly or Paladin yet.

### DL-1.4 — Network integration tests

| Field | Value |
|---|---|
| **Type** | test |
| **Phase** | Phase 1 — Network |
| **Milestone** | M1.3 |
| **Traces to** | US-002, US-003, US-011 |
| **Demo surface** | automated test |

**What it is**: `pytest` tests that prove fault tolerance and RPC consistency against the live network.

**How to try it**:
```
1. Run: `pytest -m integration -k network`
2. Expect all selected tests to pass, e.g. `2 passed` for `test_network_consistency` and `test_single_validator_failure`
```

**Verification checklist**:
- [ ] Tests pass against a freshly started network
- [ ] `ruff check .` and `mypy .` pass

**Known limitations at this phase**: test names are planned and may change.

**Phase exit gate summary** (from plan.md):
- [ ] All DL-1.x deliverables verified
- [ ] 4 validators healthy and tolerant of 1 failure
- [ ] 2 RPC nodes consistent
- [ ] `pytest -m integration` network tests pass

---

## §4 Phase 2 — FireFly + ERC-3643

**Goal**: The developer can deploy `COIN` through FireFly, onboard identities, transfer, and see the chain refuse a non-compliant transfer.

**Prerequisites**:
```
- [ ] Phase 1 exit gate passed
- [ ] Network running: `docker compose up -d`
- [ ] FireFly images pinned per spike-results.md
- [ ] T-REX contract sources and compile tooling in place (Node version per spike)
```

### DL-2.1 — FireFly in Compose

| Field | Value |
|---|---|
| **Type** | infra |
| **Phase** | Phase 2 — FireFly + ERC-3643 |
| **Milestone** | N/A |
| **Traces to** | US-004, FR-3 |
| **Demo surface** | `curl` and FireFly Explorer |

**What it is**: FireFly core, evmconnect, signer and Postgres in gateway mode, with keys `admin`, `anson`, `beatrice`.

**How to try it**:
```
1. Start: `make up` (planned name)
2. Check containers: `docker compose ps` -- FireFly services `running`
3. Status: `curl -s http://localhost:5000/api/v1/status` (port per spike)
   Expect a status document with the namespace ready.
4. Open the FireFly Explorer in a browser at the FireFly port (UI path per spike)
```

**Verification checklist**:
- [ ] FireFly status reports ready with no manual steps after `make up`
- [ ] FireFly reaches the chain through `besu-rpc-*`, not a Besu node of its own
- [ ] Three signing keys available

**Known limitations at this phase**: no contracts yet (DL-2.2).

### DL-2.2 — T-REX deployed through FireFly as `COIN`

| Field | Value |
|---|---|
| **Type** | feature |
| **Phase** | Phase 2 — FireFly + ERC-3643 |
| **Milestone** | N/A |
| **Traces to** | US-005, FR-4, UC-04 |
| **Demo surface** | CLI and file on disk |

**What it is**: Every T-REX contract needed for `COIN` is deployed using FireFly's deploy API, not a direct RPC signer.

**How to try it**:
```
1. Run: `make deploy` (planned name)
2. Open `deployed-addresses.json`
   Expect every address to be non-zero.
3. Confirm code on-chain for each address: `curl -s -X POST -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_getCode","params":["ADDRESS","latest"],"id":1}' http://localhost:8545`
   Expect a result longer than `0x`.
4. Read the token name through the FireFly contract API (path per FireFly Swagger)
   Expect `Coin`, symbol `COIN`.
```

**Verification checklist**:
- [ ] All addresses non-zero and have code
- [ ] FireFly shows a deploy operation for each contract
- [ ] Token name reads `Coin`/`COIN`
- [ ] Contracts compiled with the EVM target set in D-08

**Known limitations at this phase**: the full contract list and order come from Phase 0.

### DL-2.3 — Contract interface and API

| Field | Value |
|---|---|
| **Type** | api |
| **Phase** | Phase 2 — FireFly + ERC-3643 |
| **Milestone** | N/A |
| **Traces to** | US-006, FR-5 |
| **Demo surface** | FireFly Swagger and `curl` |

**What it is**: A FireFly contract interface and generated API for `COIN` and for the IdentityRegistry.

**How to try it**:
```
1. After `make deploy`, open FireFly's Swagger UI (path per spike)
2. Find the generated APIs for `COIN` and the IdentityRegistry
3. Call a read (`balanceOf`) and a write (`mint`) through them
   Expect the read to return a balance and the write to return an operation id.
```

**Verification checklist**:
- [ ] A read and a write both succeed through the generated API
- [ ] After `make reset && make up && make deploy`, the APIs exist again

**Known limitations at this phase**: calling raw FireFly is verbose; the CLI in Phase 4 wraps it.

### DL-2.4 — Onboarding and compliant transfer

| Field | Value |
|---|---|
| **Type** | feature |
| **Phase** | Phase 2 — FireFly + ERC-3643 |
| **Milestone** | N/A |
| **Traces to** | US-007, US-008, FR-6, UC-05, UC-06 |
| **Demo surface** | script or `pytest` (the CLI arrives in Phase 4) |

**What it is**: Admin registers and verifies Anson and Beatrice, mints 1000 `COIN` to Anson, and Anson sends `COIN` to Beatrice.

**How to try it**:
```
1. Run the onboarding step of `make deploy`
2. Check balances through the contract API
   Expect Anson 1000, Beatrice 0, both verified.
3. Transfer 25 from Anson to Beatrice through the contract API as the `anson` key
4. Re-check balances
   Expect Anson 975, Beatrice 25.
5. Re-run onboarding
   Expect no redundant transaction (no new operations for already-true steps).
```

**Verification checklist**:
- [ ] Balances change by the transfer amount
- [ ] Re-running register or claim sends no redundant transaction
- [ ] `pytest -m integration -k "onboarding or transfer"` passes

**Known limitations at this phase**: driven by script and `pytest`; the CLI lands in DL-4.1.

### DL-2.5 — On-chain compliance rejection

| Field | Value |
|---|---|
| **Type** | feature |
| **Phase** | Phase 2 — FireFly + ERC-3643 |
| **Milestone** | N/A |
| **Traces to** | US-008, FR-7, UC-07 |
| **Demo surface** | contract API and `pytest` |

**What it is**: A transfer to an unverified recipient reverts, enforced by the contract.

**How to try it**:
```
1. Confirm Admin is not verified (query `isVerified` through the contract API)
2. Send 10 `COIN` from Anson to Admin through the contract API
   Expect an operation `failed` with a revert reason about the recipient not being verified.
3. Re-check balances
   Expect no change.
```

**Verification checklist**:
- [ ] The operation fails with a revert reason
- [ ] Balances unchanged
- [ ] The same revert appears when calling the API directly, not only via a script
- [ ] `pytest -m integration -k compliance_rejection` passes

**Known limitations at this phase**: none.

### DL-2.6 — `make reset` repeatability

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
1. Run: `make reset && make up && make deploy`
2. Run: `pytest -m integration`
3. Repeat steps 1-2 two more times
```

**Verification checklist**:
- [ ] Three consecutive runs all pass
- [ ] After reset, no stale contract addresses remain in FireFly

**Known limitations at this phase**: Paladin DB is added to reset in DL-3.3.

**Phase exit gate summary** (from plan.md):
- [ ] All DL-2.x deliverables verified
- [ ] Integration tests (onboarding, transfer, rejection) pass
- [ ] Re-running register or claim sends no redundant transaction
- [ ] Reset repeatability proven

---

## §5 Phase 3 — Paladin + Noto

**Goal**: The developer can mint a private Noto token to Anson, send it to Beatrice, and show that a non-party cannot see it.

**Prerequisites**:
```
- [ ] Phase 2 exit gate passed
- [ ] Paladin image `lfdecentralizedtrust/paladin:v1.0.0` (or the tag from spike-results.md) pulled
- [ ] Hand-written Paladin config from the spike committed
```

### DL-3.1 — Paladin nodes, notary and DB

| Field | Value |
|---|---|
| **Type** | infra |
| **Phase** | Phase 3 — Paladin + Noto |
| **Milestone** | N/A |
| **Traces to** | US-009, FR-8 |
| **Demo surface** | CLI and Paladin API |

**What it is**: Two Paladin nodes (Anson, Beatrice), a notary and Paladin's database in Compose, connected to `besu-rpc-*`.

**How to try it**:
```
1. Start: `make up`
2. `docker compose ps` -- Paladin services `running`
3. Query each Paladin node's health/status endpoint (path and port per spike)
   Expect healthy and connected to Besu.
```

**Verification checklist**:
- [ ] All Paladin containers healthy
- [ ] Each reaches its Besu RPC node

**Known limitations at this phase**: the Paladin config is hand-written and may differ from the operator's output.

### DL-3.2 — Noto deploy, mint, private transfer

| Field | Value |
|---|---|
| **Type** | feature |
| **Phase** | Phase 3 — Paladin + Noto |
| **Milestone** | N/A |
| **Traces to** | US-009, FR-8, UC-08 |
| **Demo surface** | script against the Paladin API |

**What it is**: A Noto token deployed with the notary; Admin mints to Anson; Anson transfers to Beatrice.

**How to try it**:
```
1. Run the Noto script (`scripts/noto_demo.py`, planned name)
2. Query Beatrice's Paladin node for her Noto balance
   Expect the transferred amount.
3. Query Anson's node
   Expect the remainder.
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

**What it is**: Evidence that a non-party sees nothing, plus `make reset` now clearing the chain, FireFly DB and Paladin DB together.

**How to try it**:
```
1. Run: `pytest -m integration -k noto`
2. Inspect the Noto transactions on Besu: `eth_getBlockByNumber` for the relevant block, `curl` as in DL-1.3
   Expect no amounts or party addresses in the transaction data.
3. Run: `make reset && make up`
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
- [ ] `make reset` clears all three stores

---

## §6 Phase 4 — Python CLI

**Goal**: The developer can drive FireFly from a small CLI instead of raw API calls.

**Prerequisites**:
```
- [ ] Phase 3 exit gate passed
- [ ] Stack up and deployed: `make up && make deploy`
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
4. `make reset && make up && make deploy && pytest -m integration` -- repeat 3 times
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
1. `cd perf && npm install` (planned layout)
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
3. Repeat both from a fresh `make reset && make up && make deploy`
```

**Verification checklist**:
- [ ] Both reports exist
- [ ] The two runs are reproducible from a fresh stack

**Known limitations at this phase**: Caliper has no FireFly connector, so the FireFly round uses a custom HTTP workload (to be confirmed in Phase 0).

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
- [ ] Both rounds reproducible from a fresh `make reset && make up && make deploy`
- [ ] Results note committed

---

## §8 How to Run a Full End-to-End Demo

Run this after Phase 4 (Phase 5 is optional for the demo).

**1. Start the stack**
```bash
make reset
make up
make deploy
docker compose ps
```
All containers should be `running`. (`make` targets are planned names.)

**2. Walk through the primary flow**
- Show the network: DL-1.2 and DL-1.3 (kill a validator, watch the chain continue).
- Show the deploy: DL-2.2 and DL-2.3 (everything went through FireFly, check the Explorer).
- Onboard and transfer: DL-2.4, using the CLI from DL-4.1.
- Show the rejection: DL-2.5, same transfer to Admin fails with a revert reason.
- Show the private token: DL-3.2 and DL-3.3 (Beatrice sees it, a non-party does not).
- Optional: DL-5.2 and DL-5.3 for the numbers.

**3. Show the key outputs**
- `curl` against `:8545` and `:8555` shows consistent blocks and `0x0` gas price
- `deployed-addresses.json` with non-zero addresses
- CLI output with balances and the compliance error
- FireFly Explorer showing the deploy and transfer operations
- Caliper reports and the results note

**4. Tear down**
```bash
docker compose down -v
```
(or `make reset`, which clears the chain, FireFly DB and Paladin DB together). Everything resets to genesis.
