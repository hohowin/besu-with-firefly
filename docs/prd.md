# PRD: besu-with-firefly

> Source: `/grill-me` interview (2026-10-01), decisions D-01–D-15. Project-level plan and risk register: `docs/plan.md`. Architecture: `docs/architecture.md`.

## 1. Introduction/Overview

A personal learning project: the same multi-validator, multi-RPC-node Hyperledger Besu network as the earlier reference project, but with **Hyperledger FireFly** (gateway mode) and **Paladin** in place of the hand-built `mock-middleware`. FireFly is the chain transport and contract API layer. Paladin adds a private token (Noto) alongside it.

It proves four things:
1. A 4-validator QBFT network with genuine `f=1` Byzantine fault tolerance, with FireFly attached to external Besu nodes.
2. The official ERC-3643 (T-REX, with OnchainID) suite deployed through FireFly's real contract deploy process, not a Hardhat bypass.
3. A Paladin Noto private token running on the same Besu network.
4. Measured performance (Caliper) at the chain layer and the FireFly layer, so the gateway overhead is a number, not a guess.

A small Python CLI is the only client.

**Domain vocabulary** (use these terms only):
- `identity` — a demo wallet: `admin`, `anson`, `beatrice`
- `COIN` — the ERC-3643 compliance token (public ledger, deployed through FireFly)
- `contract interface` — FireFly's registered description of a contract's ABI (FFI)
- `contract API` — the REST surface FireFly generates from a contract interface
- `Noto token` — the Paladin private token; `notary` — the Paladin node that validates Noto transfers
- `verified` — an identity that is registered and holds a valid KYC claim
- `gateway mode` — FireFly running as a single node with multiple signing keys (no multi-party messaging)
- `spike` — Phase 0, the hard-gated feasibility check

## 2. Goals

- Stand up a 4-validator QBFT Besu network (`f=1`) with 2 RPC nodes (`besu-rpc-anson`, `besu-rpc-beatrice`), zero-gas, chainId `20260916`
- Provision FireFly (gateway mode) against that network using the genesis we generate, not the one `ff init` generates
- Deploy the official T-REX suite as `COIN` through FireFly's contract deploy API and expose it as a contract interface and contract API
- Run register → claim → mint → transfer through FireFly, with an on-chain compliance rejection for unverified recipients
- Run a Paladin Noto token: Admin mints to Anson, Anson transfers to Beatrice, a third party cannot see it
- Ship a Python CLI over the FireFly API
- Benchmark chain layer vs FireFly layer with Caliper
- Prove all of it with `pytest` integration tests against the live stack

## 3. Business Model

N/A. Personal local learning PoC, no monetization, no users beyond the developer.

## 4. User Stories

### US-001: Phase 0 spike resolves the four feasibility risks
**Description:** As a developer, I want each unverified risk tested before building on it, so that later phases do not rest on guesses.

**Acceptance Criteria:**
- [x] Written result for each of: (a) FireFly attaches to an external Besu (hand-written Compose) and `evmconnect` sends transactions on a `zeroBaseFee` chain; (b) Paladin nodes with hand-written config connect to external Besu and run Noto; (c) T-REX deploys through FireFly's deploy API (including the Token bytecode size check); (d) Caliper's Ethereum connector runs on the chosen Node version
- [x] Each result states feasible / not feasible and the fallback if not feasible
- [x] The EVM fork level in D-08 is confirmed or revised from what Paladin and `evmconnect` actually need
- [x] No Phase 1 work starts before this is signed off

### US-002: 4-validator QBFT network with real fault tolerance
**Description:** As a developer, I want a 4-validator QBFT genesis so the network tolerates one failed validator.

**Acceptance Criteria:**
- [ ] A generator script produces `genesis.json` with a `qbft` block listing all 4 validator addresses in `extraData`, plus 4 validator key pairs and `static-nodes.json`
- [ ] `docker compose up -d` starts 4 `besu-validator-*` containers healthy, no restart loop
- [ ] `docker stop` of any single validator leaves `eth_blockNumber` (via either RPC node) still increasing within 30s
- [ ] `eth_gasPrice` returns `0x0` on both RPC nodes

### US-003: Two independently addressable RPC nodes
**Description:** As a developer, I want two RPC nodes so Anson's and Beatrice's traffic can be shown going through distinct, identical endpoints.

**Acceptance Criteria:**
- [ ] `besu-rpc-anson` (`:8545`/`:8546`) and `besu-rpc-beatrice` (`:8555`/`:8556`) both peer with all 4 validators
- [ ] `eth_blockNumber` on both agrees within 1 block when queried 5s apart
- [ ] Neither RPC node has a `--node-private-key-file` set to a validator key

### US-004: FireFly runs in gateway mode against the external Besu network
**Description:** As a developer, I want FireFly attached to our own Besu network so the project uses FireFly's real provisioning path on our topology.

**Acceptance Criteria:**
- [ ] FireFly core, evmconnect, signer and Postgres start healthy in the same Compose stack
- [ ] FireFly signs with three keys: `admin`, `anson`, `beatrice`
- [ ] FireFly reaches the chain through `besu-rpc-*`, not through a Besu node of its own
- [ ] FireFly's own system contract/namespace setup (whatever gateway mode requires) completes without manual steps beyond `python scripts/stack.py up`
- [ ] `GET /api/v1/status` on FireFly reports ready

### US-005: T-REX deployed through FireFly as `COIN`
**Description:** As an Admin, I want the official ERC-3643 suite deployed through FireFly's contract deploy API so the deployment follows the real process.

**Acceptance Criteria:**
- [ ] Every T-REX contract needed for a working `COIN` (Token, IdentityRegistry, IdentityRegistryStorage, ClaimTopicsRegistry, TrustedIssuersRegistry, ModularCompliance, plus OnchainID and implementation-authority pieces the suite requires) is deployed through FireFly's deploy API
- [ ] Contracts compile with an EVM target compatible with the Besu fork level chosen by the spike
- [ ] A `deployed-addresses.json` records every deployed address, all non-zero
- [ ] Token name/symbol read back through FireFly as `Coin` / `COIN`
- [ ] The deploy is repeatable: after `python scripts/stack.py reset`, `python scripts/stack.py deploy` produces a working `COIN` again with no manual steps

### US-006: Contract interface and API registered in FireFly
**Description:** As a developer, I want FireFly to generate a REST API for `COIN` and the registries so the CLI never builds raw transactions.

**Acceptance Criteria:**
- [ ] A contract interface is generated from each needed ABI and registered
- [ ] A contract API exists for `COIN` and for the IdentityRegistry
- [ ] A read call (e.g. `balanceOf`) and a write call (e.g. `mint`) both succeed through FireFly's generated API
- [ ] Registrations are re-created by `python scripts/stack.py deploy` after a reset

### US-007: Onboard an identity (register → claim → mint)
**Description:** As an Admin, I want to onboard Anson and Beatrice so they can hold `COIN`.

**Acceptance Criteria:**
- [ ] Register creates the identity in the IdentityRegistry; claim makes it `verified`; mint credits `COIN`
- [ ] Re-running register or claim on an already-registered/verified identity does not error and does not send a redundant transaction (skip-if-already-true)
- [ ] After onboarding, Anson holds 1000 `COIN`, Beatrice holds 0, both `verified`
- [ ] Each write waits for FireFly to report the transaction as confirmed before the CLI reports success

### US-008: Compliant transfer, and on-chain rejection
**Description:** As Anson, I want to transfer `COIN` to Beatrice, and I want the chain to refuse a transfer to an unverified recipient.

**Acceptance Criteria:**
- [ ] Anson → Beatrice transfer succeeds; both balances change by the amount
- [ ] Transfer to an unverified address (Admin before it is verified) fails with a revert reason, and both balances are unchanged
- [ ] The rejection is raised by the contract, not by the CLI (verified by calling the contract API directly and seeing the same revert)

### US-009: Paladin Noto private token
**Description:** As a developer, I want a Noto token on Paladin so I can show a private transfer on the same Besu network.

**Acceptance Criteria:**
- [ ] Three Paladin nodes (node1 notary and registry admin, node2 Anson, node3 Beatrice) and one Postgres start healthy in the same Compose stack, connect to `besu-rpc-*`, and connect to each other over gRPC with mTLS
- [ ] The three nodes are registered in the Paladin EVM registry with their `transport.grpc` details
- [ ] A Noto token is deployed through Paladin
- [ ] Admin mints to Anson; Anson transfers to Beatrice
- [ ] Beatrice's Paladin node shows the received balance; a Paladin node that is not a party to the transfer does not
- [ ] The public Besu chain shows the Noto transactions without revealing amounts or parties (checked via the Besu RPC)

### US-010: Python CLI over FireFly
**Description:** As a developer, I want a small CLI so I can drive FireFly without curl.

**Acceptance Criteria:**
- [ ] Commands exist for: register contract interface/API, invoke (write), query (read), and show transaction/events
- [ ] `src/core/` holds the pure logic (onboarding sequencing, error classification) and defines the port; the FireFly HTTP client is an adapter that implements it
- [ ] The CLI adapter contains no business logic and calls core only
- [ ] Unit tests mock the port; no unit test touches the network
- [ ] `ruff check .`, `mypy .` and `pytest` pass

### US-011: Integration tests against the live stack
**Description:** As a developer, I want automated proof the whole stack works end to end.

**Acceptance Criteria:**
- [ ] `pytest -m integration` runs against the live stack and covers: network fault tolerance, FireFly status, T-REX deploy result, onboarding, compliant transfer, compliance rejection, Noto private transfer
- [ ] All integration tests pass across 3 consecutive runs, each after `python scripts/stack.py reset && python scripts/stack.py up && python scripts/stack.py deploy`
- [ ] No Playwright (there is no web frontend)

### US-012: Caliper benchmark, chain layer vs FireFly layer
**Description:** As a developer, I want measured throughput and latency for the chain and for FireFly, so I can see the gateway overhead.

**Acceptance Criteria:**
- [ ] A `perf/` Node sub-project (own `package.json`) runs Caliper with the Besu connector against `besu-rpc-*`
- [ ] A setup step creates N `verified` wallets with `COIN` so `Token.transfer` can run (N is configurable)
- [ ] Chain-layer round: `Token.transfer` sent directly over RPC; reports TPS and latency
- [ ] FireFly-layer round: the same transfer through FireFly's contract API using a custom Caliper connector; reports TPS and latency
- [ ] A short results note states both sets of numbers, the difference, and the genesis settings used (block period, gas limit), and states that results describe this demo configuration, not Besu's limits

## 5. Functional Requirements

**MVP:**
- FR-1: A script generates the QBFT genesis (4 validators in `extraData`), validator keys, wallet keys and `static-nodes.json`. (US-002)
- FR-2: `docker-compose.yml` defines `besu-validator-1..4` and `besu-rpc-anson`/`besu-rpc-beatrice`, all peered, `--min-gas-price=0`. (US-002, US-003)
- FR-3: FireFly runs in gateway mode against `besu-rpc-*` with signing keys `admin`, `anson`, `beatrice`. (US-004)
- FR-4: T-REX contracts are deployed only through FireFly's contract deploy API. (US-005)
- FR-5: A contract interface and contract API are registered for `COIN` and the IdentityRegistry. (US-006)
- FR-6: Onboarding is register → claim → mint, with skip-if-already-true checks. (US-007)
- FR-7: Transfers are verified by the contract; unverified recipients revert. (US-008)
- FR-8: Paladin runs three nodes (notary and registry admin, Anson, Beatrice) with one Postgres, connects to `besu-rpc-*`, registers the nodes in the EVM registry, and hosts a Noto token. (US-009)
- FR-9: The Python CLI offers register, invoke, query and show-tx/events commands over the FireFly API. (US-010)
- FR-10: Pure logic lives in `src/core/`; the FireFly client and CLI are adapters. (US-010)
- FR-11: A Python entry point `python scripts/stack.py` provides `up`, `deploy` and `reset` (Make is not used because it is not installed on Windows). `reset` clears the chain, FireFly Postgres and Paladin Postgres together. (US-004, US-005)
- FR-12: Integration tests run against the live stack and are stable across 3 fresh runs. (US-011)
- FR-13: A Caliper `perf/` project benchmarks chain layer and FireFly layer. (US-012)
- FR-14: Demo keys, genesis and wallet keys are committed and marked demo-only in the README. (README)
- FR-15: Phase 0 spike results are recorded in `docs/` before Phase 1 starts. (US-001)

**Post-MVP:**
- FR-16: Zeto (ZK) token on Paladin
- FR-17: ERC-3643 running inside a Pente privacy group
- FR-18: Paladin operations in the CLI
- FR-19: FireFly multi-party mode with two members
- FR-20: Persistent chain and DB volumes

**Future (explicitly deferred):**
- FR-21: Authentication and authorization on any API
- FR-22: A web frontend
- FR-23: Production key management (HSM/KMS)
- FR-24: Multiple asset types

## 6. Non-Goals (Out of Scope)

- A web UI or a Playwright suite (FireFly's built-in Explorer is available but not a deliverable)
- Authentication or authorization (localhost-only, accepted)
- Production key management
- Real KYC/AML
- Public or mainnet deployment
- CI/CD (local `ruff`/`mypy`/`pytest` only)
- FireFly multi-party messaging, data exchange, IPFS
- Zeto, Pente and ERC-3643-inside-Pente
- Persistent chain or DB data across `python scripts/stack.py reset`
- Using `ff init`'s own generated genesis or its single-node Clique network
- Any use of `mock-middleware`
- Kubernetes or the Paladin operator
- Business model, geographic launch, messaging channels

## 7. Design Considerations

- CLI commands are named for what they do (`register`, `invoke`, `query`, `tx`), with one FireFly endpoint behind each, so a developer can map command to API call.
- CLI output is plain text and JSON; no colour or interactive prompts, so it can be asserted in tests.

## 8. Technical Considerations

- **Stack:** Python (`ruff`, `mypy`, `pytest`) for the CLI and tests; Node.js for Caliper and contract compilation (versions set by the spike); Docker Compose for everything.
- **Layering:** per `PROJECT.md`, `src/core/` has no I/O. The FireFly HTTP client implements an interface that core defines.
- **Versions pinned:** `hyperledger/besu` image, FireFly images, `lfdecentralizedtrust/paladin:v1.0.0`. Exact tags are recorded after the spike. Do not use `kaleidoinc/paladin` (last updated Nov 2024).
- **Genesis:** produced by `besu operator generate-blockchain-config`. The `ff init` default genesis is a single-node Clique chain and does not match the target topology.
- **EVM fork:** Shanghai or later with `zeroBaseFee: true` (D-08, partially locked). T-REX is compiled with an older `evmVersion`. Confirmed or revised by the spike.
- **Deploy volume:** the official T-REX suite is many contracts and proxies, each deployed through FireFly's deploy API with its own constructor arguments.
- **Paladin config:** hand-written (the operator normally generates it). Needs Postgres (SQLite stalled the coordinator in the spike), self-signed TLS certificates with CN equal to the node name, two-phase bootstrap (deploy the registry and Noto factory, write their addresses into config, restart) and registry registration of every node. Paladin keeps its key-path index mapping in its DB, so the DB must be a volume.
- **Caliper:** version 0.6.0 (0.7.1 has no Ethereum connector), needs a `ws://` RPC URL, `web3@1.3.0` installed by hand (`caliper bind` fails on Windows), and a custom connector for the FireFly layer. A wallet setup creating N verified wallets is needed before `Token.transfer` can run; setup may take longer than the rounds.

**Non-Functional Requirements:**

| NFR | MVP target | How the architecture supports it | Tradeoff / phase gate |
|---|---|---|---|
| Availability (consensus) | Chain keeps producing blocks with 1 of 4 validators down | QBFT `n=4`, `f=1` (FR-1, FR-2) | 2 validators down halts the chain; accepted. Gate: Phase 1 |
| Consistency (RPC) | Both RPC nodes within 1 block, 5s apart | Both statically peered to all 4 validators | No partition guarantees on a local Docker network |
| Reliability (delivery) | A write sent through FireFly is confirmed or reported failed, never silently lost | FireFly's own transaction tracking; CLI waits for confirmation (FR-6) | Gap: if FireFly's DB is lost mid-flight, state is lost. Accepted for PoC |
| Performance | Measured, not targeted; numbers reported for chain layer and FireFly layer | Caliper rounds (FR-13) | Results describe this demo config (2s blocks), not Besu's limits |
| Observability | Transaction and event state visible without reading logs | FireFly Explorer and `tx`/events CLI command | No metrics or tracing stack |
| Security | No credentials outside the demo scope | Demo keys only, committed and marked demo-only | No authN/authZ anywhere; localhost-only. Gate: must be added before any non-local use |
| Operability | One command up, one command reset, including all databases | `python scripts/stack.py up`, `python scripts/stack.py deploy`, `python scripts/stack.py reset` (FR-11) | Reset deletes everything; no persistence |
| Cost | Zero | Local Docker only, no external services | n/a |

**Privacy & Data:** N/A. No real personal data. Anson, Beatrice and Admin are fictional identities. CASL, PIPEDA, GDPR and PCI do not apply.

## 9. Success Metrics

- Spike proof: 0/4 risks resolved → 4/4 with written result and fallback, by Phase 0 exit
- Fault tolerance: unverified → killing 1 of 4 validators leaves `eth_blockNumber` increasing within 30s, by Phase 1 exit
- FireFly deploy proof: 0 → `COIN` fully deployed through FireFly's deploy API and `balanceOf` read through the contract API, by Phase 2 exit
- Compliance proof: unverified → a transfer to an unverified recipient reverts on-chain and balances stay unchanged, by Phase 2 exit
- Privacy proof: unverified → a Noto transfer is visible to its parties and not to a non-party node, by Phase 3 exit
- Test stability: 0 → all integration tests green across 3 consecutive fresh-stack runs, by Phase 4 exit
- Performance: no data → chain-layer and FireFly-layer TPS and latency recorded, with the overhead stated, by Phase 5 exit

## 10. Open Questions

| # | Question | Owner | Deadline | Status |
|---|----------|-------|----------|--------|
| 1 | Does FireFly attach to an external Besu, and does `evmconnect` send transactions on a `zeroBaseFee` chain? | Howin | Phase 0 exit (2026-10-15) | Answered 2026-10-02 (see `docs/spike-results.md`) |
| 2 | Can a Paladin container with hand-written config connect to external Besu and deploy Noto? | Howin | Phase 0 exit (2026-10-15) | Answered 2026-10-02 (see `docs/spike-results.md`) |
| 3 | What EVM version do Paladin's and FireFly's own contracts need (D-08)? | Howin | Phase 0 exit (2026-10-15) | Answered 2026-10-02 (see `docs/spike-results.md`) |
| 4 | Does the official T-REX Token fit under the 24KB contract size limit, and does FireFly's deploy API accept it? | Howin | Phase 0 exit (2026-10-15) | Answered 2026-10-02 (see `docs/spike-results.md`) |
| 5 | Does Caliper's Besu connector run on a Node version compatible with the rest of the toolchain? | Howin | Phase 0 exit (2026-10-15) | Answered 2026-10-02 (see `docs/spike-results.md`) |
| 6 | Which skills to install for FireFly, Paladin and Caliper work? | Howin | Before Phase 2 starts | Open — resolved by the `/skills-required` audit |

## 11. Risks

Cross-referenced against the project risk register in `docs/plan.md` §7.

| Risk ID | Description | Mitigated by |
|---|---|---|
| R1 | FireFly will not attach to an external Besu, or `evmconnect` fails on `zeroBaseFee` | US-001 (a), fallback recorded; Phase 0 gate |
| R2 | Paladin hand-written config does not connect or deploy Noto | US-001 (b); fallback is Paladin on kind, not Paladin's own devnet Besu |
| R3 | Official T-REX exceeds contract size limits or is hard to deploy through FireFly | US-001 (c), US-005 |
| R4 | EVM fork level is wrong for Paladin or T-REX | US-001 (EVM criterion), D-08 revision path |
| R5 | No authentication anywhere | Accepted; localhost-only (FR-14, README) |
| R6 | State drift between chain, FireFly DB and Paladin DB after a partial reset | FR-11 (`python scripts/stack.py reset` clears all three) |
| R7 | Caliper setup of verified wallets dominates run time | US-012 (N configurable) |

## 12. Phase Deliverables

#### Phase 0 — Spike

| # | Deliverable | Notes |
|---|-------------|-------|
| PD-0.1 | Minimal Compose: 1 Besu + FireFly + Paladin | Throwaway, used only to test the four risks |
| PD-0.2 | `docs/spike-results.md` | One section per open question 1–5, each with feasible / not feasible and a fallback |
| PD-0.3 | Revised D-08 and D-09 if the results require it | Recorded in `docs/plan.md` |

#### Phase 1 — Network

| # | Deliverable | Notes |
|---|-------------|-------|
| PD-1.1 | Genesis/key generator script | Output: `genesis.json`, 4 validator keys, wallet keys, `static-nodes.json` |
| PD-1.2 | `docker-compose.yml` with 4 validators and 2 RPC nodes | Zero-gas confirmed |
| PD-1.3 | Fault-tolerance and RPC-consistency integration tests | `pytest -m integration` |

#### Phase 2 — FireFly + ERC-3643

| # | Deliverable | Notes |
|---|-------------|-------|
| PD-2.1 | FireFly (gateway mode) service definitions in Compose | |
| PD-2.2 | T-REX contracts and compile config | EVM target set by the spike |
| PD-2.3 | `python scripts/stack.py deploy`: deploys through FireFly, registers interface and API, onboards Admin/Anson/Beatrice | Writes `deployed-addresses.json` |
| PD-2.4 | Integration tests: onboarding, transfer, compliance rejection | |

#### Phase 3 — Paladin + Noto

| # | Deliverable | Notes |
|---|-------------|-------|
| PD-3.1 | Paladin service definitions: 3 nodes (notary, Anson, Beatrice), one Postgres, demo TLS certificates | Image `lfdecentralizedtrust/paladin:v1.0.0` |
| PD-3.2 | Noto deployment and mint/transfer script | |
| PD-3.3 | Integration test: party sees balance, non-party does not | |

#### Phase 4 — Python CLI

| # | Deliverable | Notes |
|---|-------------|-------|
| PD-4.1 | `src/core/` (pure logic and port) | No I/O |
| PD-4.2 | FireFly HTTP adapter and CLI adapter | CLI has 4 commands |
| PD-4.3 | Unit tests (mocked port) and integration tests | 3 fresh-stack runs green |

#### Phase 5 — Caliper

| # | Deliverable | Notes |
|---|-------------|-------|
| PD-5.1 | `perf/` Node sub-project with benchmark config | |
| PD-5.2 | Wallet setup step | N verified wallets with `COIN` |
| PD-5.3 | Chain-layer and FireFly-layer rounds | Custom Caliper connector for FireFly |
| PD-5.4 | Results note | Numbers, overhead, genesis settings, caveat |
