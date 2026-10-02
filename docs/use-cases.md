# Use Cases — besu-with-firefly

> **Owner:** Howin Ho · **Created:** 2026-10-01 · **Status:** Draft
> Companion docs: [prd.md](prd.md) · [architecture.md](architecture.md) · [plan.md](plan.md)

This document is the single reference for end-to-end interaction flows.

Names follow `architecture.md`. Where a FireFly or Paladin behaviour is not yet verified, the use case says so and points at the Phase 0 spike. There is no web frontend, so there are no Playwright specs. Each use case names the `pytest -m integration` test that should cover it.

---

## Actors

| Actor | Role |
|---|---|
| Developer | Runs the stack script (`python scripts/stack.py`), the CLI and Caliper. The only human user |
| Admin | Demo identity. Plays Token Agent and Trusted Issuer (registers, claims, mints) |
| Anson | Demo identity. Holds `COIN` and a Noto balance |
| Beatrice | Demo identity. Receives transfers |
| CLI | Python CLI: CLI adapter, `core`, FireFly adapter (see architecture §2) |
| FireFly | Gateway mode, single node. Deploys contracts, generates the contract API, signs for admin, anson, beatrice |
| Paladin node1 / node2 / node3 | node1 is the notary and registry admin, node2 is Anson, node3 is Beatrice. They host the Noto token and talk over gRPC with mTLS. Peers are found through the on-chain EVM registry |
| Besu network | 4 validators plus `besu-rpc-anson` and `besu-rpc-beatrice` |
| T-REX contracts | On-chain compliance suite, the real authorization boundary |
| Caliper | Benchmark tool in `perf/` |

---

## UC-01: Run the Phase 0 spike

**Goal:** The developer knows whether each risky assumption holds and has a fallback for each one that does not.

**Trigger:** The developer starts Phase 0.

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant SB as Minimal Compose
    participant FF as FireFly
    participant PA as Paladin
    participant BS as Besu single node
    participant CAL as Caliper

    Note over Dev,CAL: Risk 1 - FireFly on external Besu
    Dev->>SB: start Besu with zeroBaseFee genesis
    Dev->>FF: attach with hand-written Compose config
    Dev->>FF: invoke a test contract write
    FF->>BS: send transaction via evmconnect
    alt operation succeeds
        BS-->>FF: receipt ok
        FF-->>Dev: succeeded
    else fails
        FF-->>Dev: failed, record fallback
    end

    Note over Dev,CAL: Risk 3 - T-REX through FireFly deploy API
    Dev->>FF: deploy small contract, then Token
    FF-->>Dev: addresses and bytecode size

    Note over Dev,CAL: Risk 2 - Paladin hand-written config
    Dev->>PA: start with config pointing at Besu
    Dev->>PA: deploy Noto and mint
    alt Paladin healthy
        PA-->>Dev: Noto mint completes
    else cannot connect
        PA-->>Dev: record fallback, Paladin on kind
    end

    Note over Dev,CAL: Risk 4 - Caliper
    Dev->>CAL: run trivial round against Besu
    CAL-->>Dev: report and Node version

    Dev->>Dev: write spike-results.md and revise D-08, D-09
```

**Notes:**
- Traces to US-001, FR-15, plan.md Phase 0 and D-15.
- Hard gate: no Phase 1 work until each risk has a result and a fallback.
- Also records the EVM version Paladin and FireFly contracts need (D-08).
- Test: none, the output is a document.

---

## UC-02: Generate and start the network

**Goal:** A 4-validator QBFT network with 2 RPC nodes is running and consistent.

**Trigger:** Developer runs `python scripts/stack.py up`.

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant GEN as network generator
    participant BC as besu operator generate-blockchain-config
    participant DC as Docker Compose
    participant VAL as validators 1 to 4
    participant RPC as besu-rpc-anson and besu-rpc-beatrice

    Note over Dev,RPC: Generate once
    Dev->>GEN: stack up
    GEN->>BC: generate genesis and 4 validator keys
    BC-->>GEN: genesis.json with extraData
    GEN->>GEN: write static-nodes.json and wallet keys

    Note over Dev,RPC: Start
    GEN->>DC: docker compose up
    DC->>VAL: start with own key, genesis, static-nodes
    VAL->>VAL: peer, QBFT rounds, seal block every 2s
    DC->>RPC: start with no validator key
    RPC->>VAL: dial validators and sync from block 0

    Note over Dev,RPC: Check
    Dev->>RPC: eth_blockNumber on both, 5s apart
    alt within 1 block and gas price 0x0
        RPC-->>Dev: consistent
    else diverged
        RPC-->>Dev: stop, re-check extraData against validator keys
    end
```

**Notes:**
- Traces to US-002, US-003, FR-1, FR-2. Plan D-01, D-03.
- A node is a validator because of its key, not its container name; the RPC nodes have no validator key.
- Demo keys are committed (D-10).
- Test: `test_network_consistency`.

---

## UC-03: Survive a validator failure

**Goal:** Show that the chain keeps producing blocks with 1 of 4 validators down.

**Trigger:** Developer stops one validator container.

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant DC as Docker Compose
    participant VAL as remaining validators
    participant RPC as besu-rpc-anson

    Dev->>RPC: eth_blockNumber, note value N
    Dev->>DC: docker stop besu-validator-4
    Note over VAL: 3 of 4 can still commit, f is 1
    loop within 30 seconds
        Dev->>RPC: eth_blockNumber
    end
    alt height greater than N
        RPC-->>Dev: chain advancing
        Dev->>DC: docker start besu-validator-4
        DC->>VAL: validator rejoins
    else height stuck
        RPC-->>Dev: f equals 1 premise broken, check genesis extraData
    end
    Note over Dev,RPC: Stopping 2 validators halts the chain, accepted risk R10
```

**Notes:**
- Traces to US-002, NFR Availability. Plan Phase 1 anti-gate.
- Test: `test_single_validator_failure`.

---

## UC-04: Deploy the T-REX suite through FireFly

**Goal:** `COIN` and its registries are deployed through FireFly's real deploy process and exposed as a contract API.

**Trigger:** Developer runs `python scripts/stack.py deploy` on a fresh stack.

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CLI as CLI
    participant FF as FireFly
    participant SG as FireFly signer
    participant RPC as besu-rpc-anson
    participant CH as Besu network

    Note over Dev,CH: Compile (host tooling, no deployment)
    Dev->>CLI: stack deploy
    CLI->>CLI: read ABI and bytecode of each T-REX contract

    Note over Dev,CH: Deploy each contract
    loop each contract in dependency order
        CLI->>FF: contract deploy API with bytecode and constructor args
        FF->>SG: sign with admin key
        SG->>RPC: eth_sendRawTransaction
        RPC->>CH: QBFT block
        CH-->>FF: receipt with contract address
        FF-->>CLI: operation succeeded plus address
    end
    Note over CLI: Spike checks Token bytecode size and deploy API fit

    Note over Dev,CH: Register interface and API
    CLI->>FF: generate contract interface from ABI
    CLI->>FF: register interface
    CLI->>FF: create contract API for COIN and IdentityRegistry
    FF-->>CLI: API names and URLs

    alt all addresses non-zero and name reads Coin
        CLI->>FF: query name via contract API
        FF-->>CLI: Coin
        CLI-->>Dev: deployed-addresses.json written
    else a deploy failed
        CLI-->>Dev: stop with the failing contract and revert reason
    end
```

**Notes:**
- Traces to US-005, US-006, FR-4, FR-5. Plan D-04.
- Deploy goes through FireFly, not a direct RPC signer, so FireFly tracks the contracts (architecture §7 B).
- Order matters: registries and implementation authority before Token and ModularCompliance. The exact list comes from the Phase 0 deploy results.
- Contracts are compiled with the EVM target from D-08.
- Test: `test_trex_deployed_through_firefly`.

---

## UC-05: Onboard an identity

**Goal:** An identity is registered, verified and holds `COIN`.

**Trigger:** Developer runs the onboard command for Anson (and later Beatrice).

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CLI as CLI core
    participant FF as FireFly contract API
    participant IR as IdentityRegistry
    participant TK as Token COIN

    Dev->>CLI: onboard anson with amount 1000

    Note over Dev,TK: Step 1 - register
    CLI->>FF: query isRegistered(anson)
    FF->>IR: eth_call
    alt not registered
        CLI->>FF: invoke registerIdentity as admin
        FF->>IR: transaction
        FF-->>CLI: operation succeeded
    else already registered
        Note over CLI: skip, no transaction sent
    end

    Note over Dev,TK: Step 2 - claim
    CLI->>FF: query isVerified(anson)
    alt not verified
        CLI->>FF: invoke issueClaim as admin, KYC topic
        FF->>IR: transaction
        FF-->>CLI: operation succeeded
    else already verified
        Note over CLI: skip
    end

    Note over Dev,TK: Step 3 - mint
    CLI->>FF: invoke mint(anson, 1000) as admin
    FF->>TK: transaction
    alt recipient verified
        TK-->>FF: mined
        FF-->>CLI: succeeded
        CLI-->>Dev: anson verified, balance 1000
    else not verified
        TK-->>FF: revert recipient not verified
        FF-->>CLI: failed with revert reason
        CLI-->>Dev: compliance error
    end
```

**Notes:**
- Traces to US-007, FR-6. Architecture §8 orchestration sequence.
- Skip-if-already-true avoids paying a block wait for a call that would be a no-op. The contract remains the final backstop.
- Beatrice is onboarded the same way with amount 0 (verified, no mint) so that later transfers to her succeed.
- Test: `test_onboarding_is_idempotent`.

---

## UC-06: Compliant transfer

**Goal:** Anson sends `COIN` to Beatrice and the balances change.

**Trigger:** Developer runs the transfer command acting as Anson.

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CLI as CLI core
    participant FF as FireFly
    participant SG as FireFly signer
    participant TK as Token COIN

    Dev->>CLI: transfer 25 from anson to beatrice
    CLI->>FF: invoke transfer as anson
    FF->>SG: sign with anson key
    SG->>TK: transfer(beatrice, 25)
    FF-->>CLI: operation pending

    loop poll until final or timeout
        CLI->>FF: get operation status
    end

    alt succeeded
        FF-->>CLI: succeeded
        CLI->>FF: query balanceOf anson and beatrice
        FF-->>CLI: 975 and 25
        CLI-->>Dev: transfer sent, balances shown
    else failed
        FF-->>CLI: failed with reason
        CLI-->>Dev: error, balances unchanged
    else timeout
        CLI-->>Dev: pending or unknown with transaction id, never success
    end
```

**Notes:**
- Traces to US-008, FR-7, FR-9. Architecture §3 critical path and §5 lifecycle.
- The CLI names the acting identity in its output.
- Test: `test_transfer_between_verified_identities`.

---

## UC-07: Transfer rejected by compliance

**Goal:** A transfer to an unverified recipient fails on-chain and nothing moves.

**Trigger:** Developer sends from Anson to Admin while Admin is not verified.

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CLI as CLI core
    participant FF as FireFly
    participant TK as Token COIN
    participant IR as IdentityRegistry

    Dev->>CLI: transfer 10 from anson to admin
    CLI->>FF: invoke transfer as anson
    FF->>TK: transaction
    TK->>IR: isVerified(admin)
    IR-->>TK: false
    TK-->>FF: revert recipient not verified
    FF-->>CLI: operation failed with revert reason
    CLI-->>Dev: compliance error, balances unchanged

    Note over Dev,TK: Proof the CLI is not the gate
    Dev->>FF: call the contract API directly with the same transfer
    FF-->>Dev: same revert
```

**Notes:**
- Traces to US-008, FR-7. Plan Phase 2 anti-gate.
- The direct call proves the contract, not the CLI, enforces compliance.
- Admin is a real, currently unverified identity in the demo, so this is a genuine rejection, not a fabricated error.
- Test: `test_compliance_rejection`.

---

## UC-08: Private Noto mint and transfer

**Goal:** Node1 (notary) mints a private token to Anson, Anson sends part of it to Beatrice, and Beatrice cannot see Anson's other coins.

**Trigger:** Developer runs the Noto script (Paladin API, not the CLI in v1).

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant N1 as Paladin node1 notary
    participant N2 as Paladin node2 Anson
    participant N3 as Paladin node3 Beatrice
    participant REG as EVM registry
    participant BS as Besu network

    Note over Dev,BS: Bootstrap - contracts and registry
    Dev->>N1: deploy registry, noto, noto-factory and proxy using node1 keys
    N1->>BS: public transactions
    Dev->>N1: write the contract addresses into every node config and restart
    Dev->>N1: register node1, node2 and node3 as registry admin
    N1->>REG: registerIdentity for each node
    Dev->>N2: publish transport.grpc with local transport details
    N2->>REG: setIdentityProperty with endpoint and issuer certificate
    Note over N1,N3: node1 and node3 publish their transport details the same way

    Note over Dev,BS: Setup
    Dev->>N1: deploy Noto token, notary node1, basic mode
    N1->>BS: base ledger transaction
    BS-->>N1: token address

    Note over Dev,BS: Mint
    Dev->>N1: mint 100 to anson on node2
    N1->>REG: look up node2 transport
    N1->>N2: private delivery of the coin state over gRPC mTLS
    N1->>BS: base ledger transaction with hashes only

    Note over Dev,BS: Private transfer
    Dev->>N2: transfer 40 from anson to beatrice on node3
    N2->>N1: delegate to the coordinator, notary endorses
    N1->>N3: private delivery of the 40 coin state
    N1->>BS: base ledger transaction with hashes only

    Note over Dev,BS: Check privacy
    Dev->>N3: list coin states
    N3-->>Dev: 40 only
    Dev->>N2: list coin states
    N2-->>Dev: 40, 60 and 100
    Dev->>N1: list coin states
    N1-->>Dev: 40, 60 and 100 as notary
    Dev->>BS: inspect the Noto token logs
    BS-->>Dev: no plain amounts
```

**Notes:**
- Traces to US-009, FR-8. Plan D-05, D-09, Phase 3. Proven in the Phase 0 spike (`docs/spike-results.md`, Risk 2) with exactly these results.
- Paladin needs Postgres. With SQLite the coordinator stalled and the transfer never completed.
- Key addresses are not reproducible from the mnemonic alone, because Paladin stores the path index mapping in its DB. Keep the DB across restarts, and deploy the registry after the DB exists.
- The delegation to the coordinator in the transfer step was seen in the node logs. Which node coordinates is decided by Paladin.
- All Paladin nodes run on one host, so this demonstrates the protocol, not real isolation (risk R11).
- Test: `test_noto_private_transfer`.

---

## UC-09: Reset the stack

**Goal:** Return to a clean state with the chain, FireFly and Paladin consistent.

**Trigger:** Developer runs `python scripts/stack.py reset`.

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant MK as stack reset
    participant DC as Docker Compose
    participant ST as Besu data, FireFly Postgres, Paladin Postgres

    Dev->>MK: stack reset
    MK->>DC: docker compose down with volumes
    DC->>ST: delete chain data, FireFly DB, Paladin Postgres
    Dev->>MK: stack up
    MK->>DC: start from generated genesis
    Dev->>MK: stack deploy
    MK->>DC: deploy T-REX through FireFly, register API, onboard identities
    alt all three stores cleared together
        DC-->>Dev: working COIN on a fresh chain
    else only one cleared
        DC-->>Dev: stale addresses or unknown contracts, treat as bug R6
    end
```

**Notes:**
- Traces to FR-11, plan R6. Plan Phase 2 step 7 and Phase 3 step 5.
- Reset is also the setup for every integration run (US-011).
- Test: `test_reset_repeatability` runs this three times.

---

## UC-10: Benchmark chain layer vs FireFly layer

**Goal:** Produce comparable TPS and latency for direct RPC and for FireFly, and state the difference.

**Trigger:** Developer runs the Caliper rounds in `perf/`.

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CAL as Caliper
    participant WS as wallet setup
    participant FF as FireFly
    participant RPC as besu-rpc-anson

    Note over Dev,RPC: Setup
    Dev->>CAL: run with N wallets
    CAL->>WS: create N wallets
    WS->>FF: register, claim, mint for each wallet
    FF-->>WS: N verified wallets with COIN

    Note over Dev,RPC: Round 1 - chain layer
    CAL->>RPC: Token.transfer direct over JSON-RPC
    RPC-->>CAL: receipts
    CAL-->>Dev: TPS and latency

    Note over Dev,RPC: Round 2 - FireFly layer
    CAL->>FF: same transfer through contract API (custom connector)
    FF->>RPC: via signer
    RPC-->>FF: receipts
    FF-->>CAL: operation status
    CAL-->>Dev: TPS and latency

    Dev->>Dev: write results note with difference and genesis settings
```

**Notes:**
- Traces to US-012, FR-13. Plan D-14, Phase 5.
- Setup can take longer than the rounds themselves (risk R7).
- Results describe this demo configuration (2s blocks, gas limit), not Besu limits (R13).
- Caliper has no FireFly connector, so round 2 uses a small custom connector (proven in Phase 0). Caliper 0.6.0 is used because 0.7.1 dropped the Ethereum connector.
- Test: none pass/fail. The check is that both reports exist and the note states the configuration.

---

## UC-11: Handle a write that does not finish

**Goal:** The CLI never claims success for a write whose final status is unknown.

**Trigger:** A FireFly write stays pending past the CLI timeout.

```mermaid
sequenceDiagram
    actor Dev as Developer
    participant CLI as CLI core
    participant FF as FireFly
    participant BS as Besu network

    Dev->>CLI: invoke mint
    CLI->>FF: invoke contract API
    FF-->>CLI: operation pending, transaction id
    loop until timeout
        CLI->>FF: get operation status
        FF-->>CLI: pending
    end
    CLI-->>Dev: pending or unknown, transaction id, exit non-zero

    Note over Dev,BS: Later
    Dev->>CLI: show transaction by id
    CLI->>FF: get operation and events
    alt now succeeded
        FF-->>CLI: succeeded
        CLI-->>Dev: succeeded
    else now failed
        FF-->>CLI: failed with reason
        CLI-->>Dev: failed
    end
```

**Notes:**
- Traces to US-010, FR-9. Architecture §5 lifecycle and §3 failure handling.
- Re-sending the same write is safe for onboarding because UC-05 checks state first. For other writes, FireFly idempotency options are an open question (plan Q7).
- Test: `test_cli_never_reports_success_from_pending`, unit test with a mocked port.

---

## Coverage

| UC | User stories | Test |
|---|---|---|
| UC-01 | US-001 | document |
| UC-02 | US-002, US-003 | `test_network_consistency` |
| UC-03 | US-002 | `test_single_validator_failure` |
| UC-04 | US-005, US-006 | `test_trex_deployed_through_firefly` |
| UC-05 | US-007 | `test_onboarding_is_idempotent` |
| UC-06 | US-008 | `test_transfer_between_verified_identities` |
| UC-07 | US-008 | `test_compliance_rejection` |
| UC-08 | US-009 | `test_noto_private_transfer` |
| UC-09 | US-004, US-005 | `test_reset_repeatability` |
| UC-10 | US-012 | report files |
| UC-11 | US-010 | unit test, mocked port |

All use cases are MVP. Post-MVP flows (Zeto, Pente, Paladin in the CLI, multi-party) have no use case yet and would need a new `/grill-me` pass.
