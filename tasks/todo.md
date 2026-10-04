# Tasks — Phase 3: Paladin + Noto

> Source: `docs/plan.md` Phase 3 (steps 1 to 6), `docs/prd.md` US-009 and FR-8, `docs/deliverables.md` DL-3.1 to DL-3.3, `docs/use-cases.md` UC-08, `docs/spike-results.md` (Risk 2 and "Versions to pin"), and the working spike in `spike/paladin/`. Decisions: D-05 (Noto only, three nodes), D-09 (Compose, `lfdecentralizedtrust/paladin:v1.0.0`, hand-written config, Postgres, self-signed TLS, DB volume), D-10 (demo keys committed), D-16 (`python scripts/stack.py`). Phases 1 and 2 are complete and reviewed; their lists are `tasks/phase-1-network.md` and `tasks/phase-2-firefly.md`.
> **Status: approved by Howin on 2026-10-03 (all Open Questions answered as recommended).** Updated 2026-10-03: the network is now 1 validator and 1 RPC node (plan D-17), so the stack is 6 containers today and 10 with Paladin.

## Overview

Phase 3 adds Paladin next to FireFly on the same Besu network: three Paladin nodes (node1 notary and registry admin, node2 Anson, node3 Beatrice) and one Postgres, then a Noto private token that is minted to Anson and transferred to Beatrice, with proof that a node which is not a party does not see it and that the public chain shows no amounts. The spike already proved all of this on one node of a throwaway chain; this phase rebuilds it inside the real stack so that `up`, `deploy` and `reset` handle it with no manual step, and tests keep it proven.

The one structural difficulty is the **two-phase bootstrap** found in the spike: Paladin can only be given its Noto domain and registry once those contracts exist, and they are deployed through Paladin node1 itself. So the nodes first start with a config that has no domain, `deploy` then deploys the registry and Noto contracts, writes the addresses into each node's config, restarts the nodes, and registers them in the registry.

Design choices that apply to every task:
- **Layers (`PROJECT.md`).** Pure logic in `src/core/paladin/` (config text, bootstrap plan, registry steps, Noto request bodies, privacy checks on coin lists). I/O in `src/adapters/` (Paladin JSON-RPC client, certificate generation in the Paladin image, file writing, Docker) and `scripts/stack.py`.
- **Paladin is a second, independent path to the chain.** It shares Besu with FireFly but not FireFly; its contracts are deployed by its own derived keys through its own RPC, not through FireFly.
- **Generated material is committed** (D-10), like the FireFly material: per-node mnemonics, TLS certificates, base config and the Postgres init script under `network-config/paladin/`, created by `init`.
- **Key derivation depends on the database.** Paladin hands out BIP32 path indexes in the order it first resolves key names and stores them in its DB, so the Postgres volume must survive a plain restart, and any DB wipe must come with a chain wipe (`reset` does both). The bootstrap order is therefore fixed and must not change between runs.
- **Image facts (read from `lfdecentralizedtrust/paladin:v1.0.0`):** it has `curl` and `openssl`, runs as uid 1001, needs `/app/jna` writable and executable (`tmpfs: /app/jna:exec,mode=1777`), and does **not** contain the registry and Noto contract artifacts (those come from the release assets).
- **Tests.** Unit tests need no Docker. Integration tests use the real stack. The gate is `pytest -m integration` (the fault-injection tests were removed on 2026-10-03 with the move to one validator, plan D-17). Each Noto test deploys its own token, so tests do not depend on each other's state.
- **Verification commands** (from `PROJECT.md`): `ruff check .`, `mypy .`, `pytest`, `pytest -m integration`, `docker compose config -q`.
- **Working branch:** `main`, committing per task.

Sizes: no task is L or larger. Tasks 1, 5 and 7 are the largest (M).

---

## Group A — Paladin nodes run (plan step 1, DL-3.1)

### Task 1: `init` generates the Paladin material

**Description:** Extend `stack.py init` so it also writes, under `network-config/paladin/`: per node (`node1` to `node3`) a BIP39 mnemonic (demo; made with `eth-account`'s HD wallet support), a self-signed TLS certificate and key whose subject CN is the node name (`basicConstraints CA:TRUE`, `keyUsage digitalSignature,keyCertSign`, `extendedKeyUsage serverAuth,clientAuth`, and `ca.crt` the same certificate, as the spike found the gRPC transport requires), the **base** node config (no domain and no registry, so it starts before the contracts exist), and the Postgres init script that creates `node1`, `node2` and `node3`. Config text is built by pure functions in `src/core/paladin/`. The certificates are made with `openssl` inside the pinned Paladin image through Docker, injected like the Besu generator, so there is no new Python dependency. Same refuse-without-`--force` rule as before.

**Acceptance criteria:**
- [x] Each certificate has CN equal to its node name, is a CA with SAN `paladin-nodeN`, and can both sign and authenticate as server and client, checked with `openssl x509` in an integration test
- [x] Each mnemonic is a valid 12-word BIP39 phrase and the three are different; the base config has the right node name, the Besu endpoints, the Postgres DSN for its own database, TLS paths and gRPC port, and contains no `domains` or `registries` block (unit-tested on the pure builder)
- [x] `init` without `--force` still refuses and changes nothing; with `--force` everything is regenerated consistently

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k init`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** None (Phases 1 and 2 done)

**Files likely touched:**
- `src/core/paladin/config.py`, `src/core/paladin/mnemonic.py`
- `src/adapters/besu_config.py` (or a sibling adapter), `src/adapters/paladin_files.py`
- `network-config/paladin/` (generated, committed, demo only), `network-config/README.md`
- `tests/unit/core/test_paladin_config.py`, `tests/unit/adapters/test_paladin_files.py`, `tests/integration/test_init.py`

**Size:** M

**Status:** Done 2026-10-03. Test-first (23 new unit tests, 1 new integration test; 302 unit tests in all). Pure `src/core/paladin/config.py` builds the base config (matching the spike, log level `info`, no `domains` or `registries`, all three nodes using `besu-rpc-anson`) and the Postgres init script; `src/adapters/paladin_files.py` writes `network-config/paladin/<node>/pldconf.paladin.yaml`, `certs/` and `postgres-init/init.sql`, with a fresh 12-word BIP39 mnemonic per node from `eth-account`. Certificates are made with `openssl` inside the pinned Paladin image (P-256, self-signed, own CA, 10 years), the profile read from the spike's working certificates. `init_network` now requires a `cert_maker` (tests pass a fake). The committed `network-config/` got only the new `paladin/` folder (made with the same function) instead of a full `init --force`, so the existing demo keys and the deployed addresses stay as they are.

### Task 2: Paladin and Postgres containers start and answer

**Description:** Add `paladin-postgres` (`postgres:17-alpine`, one server, a database per node, data on a volume so a plain restart keeps it) and `paladin-node1` to `paladin-node3` to `docker-compose.yml`, image pinned to `lfdecentralizedtrust/paladin:v1.0.0`, mounting each node's config from a runtime folder and its certificates, with the `/app/jna` tmpfs, starting after Postgres is healthy. The nodes read their config from `paladin-runtime/nodeN/` (gitignored); `stack.py up` copies the committed base config there when it is missing, so a fresh clone needs no extra step (Open Question 4). All three nodes talk to `besu-rpc-anson`, the only RPC node (Open Question 1). Publish only each node's HTTP RPC port (`8548`, `8648`, `8748`; Open Question 6). Healthcheck: `curl` of `transport_nodeName` inside the container. Log level `info` (Open Question 7).

**Acceptance criteria:**
- [x] `docker compose config -q` exits 0, and `python scripts/stack.py up` brings the 3 nodes and Postgres to `healthy` along with the existing 10 services, with no restart loop
- [x] `transport_nodeName` on ports `8548`, `8648` and `8748` returns `node1`, `node2` and `node3`
- [x] Each node is connected to its Besu RPC node and has indexed blocks (confirmed with Paladin's `bidx_queryIndexedBlocks`, and that its newest indexed block keeps rising)

**Verification:**
- [x] Tests pass: `pytest -m integration -k paladin_nodes` (new test, red before the Compose change)
- [x] Checks clean: `docker compose config -q`, `ruff check .`, `mypy .`

**Dependencies:** Task 1

**Files likely touched:**
- `docker-compose.yml`
- `src/adapters/stack_cli.py` (seed `paladin-runtime/` from the base config), `.gitignore`
- `tests/integration/test_paladin_nodes.py`, `tests/support/paladin.py` (a tiny JSON-RPC helper for tests)

**Size:** M

**Status:** Done 2026-10-03. Test-first (7 new unit tests, 11 new integration tests). `docker-compose.yml` has `paladin-postgres` (`postgres:17-alpine`, init script mounted, data on the named volume `paladin-postgres-data`) and `paladin-node1` to `paladin-node3` (shared `x-paladin` anchor: pinned image, `/app/jna` tmpfs with exec, `curl` healthcheck of `transport_nodeName`, started after Postgres and the RPC node are healthy), ports `8548`, `8648` and `8748`. `stack.py up` seeds `paladin-runtime/<node>/` from the committed base config first (never overwriting a config `deploy` has written, and saying to run `init` if the material is missing); `stack.py reset` now also removes `paladin-runtime/` (moved here from Task 11 because a stale final config would otherwise outlive the chain). On the real stack all four containers were healthy on the first try, with no change to Besu's RPC API list. A cold `reset` and `up` of all 10 containers took 108 s (59 to 107 s before Paladin). The Paladin logs show start-up noise (`Plugin loader stream error`, `Unknown channel option SO_KEEPALIVE`, and `eth_getBlockReceipts` returning null while the block indexer catches up); nodes still index every block. The whole suite from a fresh `reset`, `up`, `deploy`: 66 passed in 6 min 21 s.

## Checkpoint: After Tasks 1–2

- [x] `ruff check .`, `mypy .` and `pytest` clean (309 unit tests)
- [x] `python scripts/stack.py reset && python scripts/stack.py up` leaves 10 healthy containers (6 before plus 4 Paladin), the three Paladin nodes answering and connected to Besu
- [x] The Phase 1 and 2 tests still pass (`pytest -m integration`: 66 passed from a fresh `reset`, `up`, `deploy`); effect of four more containers on start time: cold `up` 108 s (59 to 107 s before)
- [x] Human review before proceeding (Howin, 2026-10-03: ok)

---

## Group B — Bootstrap and registry (plan step 2)

### Task 3: Pinned Paladin contract artifacts and private Noto ABI

**Description:** Vendor the four smart-contract artifacts the Paladin operator deploys (`registry`, `noto`, `noto_factory`, `noto_factory_proxy`, from the v1.0.0 `artifacts.tar.gz` release asset) and the private Noto ABI `INotoPrivate.json` (from `abis.tar.gz`) under `contracts/paladin/`, unchanged, with a short note giving the source URLs, the release, the licence (Apache-2.0) and their SHA-256 sums. Add a loader in `src/adapters/paladin_artifacts.py` that reads each artifact's ABI and bytecode (a small parser, tested on the real files) and the private ABI, plus a test that fails if a vendored file no longer matches its recorded SHA-256. Check every deployed size against the 24,576-byte limit, as for T-REX.

**Acceptance criteria:**
- [x] The loader returns a non-empty ABI and bytecode for all four contracts; constructors match what the operator deploys: the registry takes one argument (`[false]`), the proxy two (the factory and the `initialize(noto)` call data), Noto and the factory none
- [x] Each vendored file matches its recorded SHA-256, and every init code is under the Shanghai limit (the artifacts hold init code only; the runtime size is checked on chain in Task 5)
- [x] The private Noto ABI contains `mint`, `transfer` and `balanceOf`

**Verification:**
- [x] Tests pass: `pytest tests/unit`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** None (can run in parallel with Tasks 1 and 2)

**Files likely touched:**
- `contracts/paladin/` (4 artifact YAML files, `INotoPrivate.json`, `README.md` with sources and SHA-256)
- `src/adapters/paladin_artifacts.py`
- `tests/unit/adapters/test_paladin_artifacts.py`

**Size:** S

**Status:** Done 2026-10-03. Test-first (17 tests). Downloaded `artifacts.tar.gz` and `abis.tar.gz` from the Paladin v1.0.0 release; the four contract files are byte for byte the ones the spike used, and `INotoPrivate.json` is new. They are vendored unchanged under `contracts/paladin/` with `SHA256SUMS` and a README (source URLs, tarball hashes checked against the real files, Apache-2.0, how to refresh). Pure `src/core/paladin/artifacts.py` parses the Kubernetes-style YAML without a YAML library and also reads from each file the key label that sends it (`registry.operator`, `noto.operator`, ...), its `paramsJSON` and `requiredContractDeployments`, which the tests compare with the operator's order. Init code sizes: registry 5,343, Noto 11,515, factory 4,267, proxy 691 bytes.

### Task 4: Paladin JSON-RPC client

**Description:** A small adapter in `src/adapters/paladin.py` (standard library only) for the calls this phase needs: a generic `call(node, method, params)` with a clear error carrying Paladin's own message, `ptx_sendTransaction` followed by bounded polling of `ptx_getTransactionReceipt`, and `ptx_call`. The transport is injected so unit tests need no Docker. Pure parts (building the request, reading a receipt as success or failure, classifying transient errors such as a timeout so they are retried) are in `src/core/paladin/`.

**Acceptance criteria:**
- [x] With a fake transport: a JSON-RPC error raises with Paladin's message, a successful receipt returns, a failed receipt raises with its text, a receipt that never arrives times out naming the transaction id, and a transient error is retried while an error from the contract is not
- [x] Against the live nodes, `transport_nodeName` round-trips on all three
- [x] The module has no hidden global state and no `print`

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k paladin_client`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 2

**Files likely touched:**
- `src/core/paladin/rpc.py`, `src/adapters/paladin.py`
- `tests/unit/core/test_paladin_rpc.py`, `tests/unit/adapters/test_paladin.py`, `tests/integration/test_paladin_client.py`

**Size:** S

**Status:** Done 2026-10-03. Test-first (24 unit tests with a fake transport, 6 integration tests). Pure `src/core/paladin/rpc.py` (request body, `unwrap` of a JSON-RPC reply, receipt classification, transient-error test) and `src/adapters/paladin.py` (`PaladinClient`: `call` retried up to 3 times on a timeout, `send_transaction` never retried, `send_and_wait` polling `ptx_getTransactionReceipt` with a bound, `private_call` over `ptx_call`; `TransactionFailed` and `ReceiptTimeout` carry the transaction id). Real behaviour seen: an unsupported method is `-32600` `PD020702: method not supported`, and the receipt of an unknown transaction is `null` (not an error). 350 unit tests in all.

### Task 5: Deploy the registry and Noto contracts, then restart the nodes with their domain

**Description:** Extend `stack.py deploy` with a Paladin phase (run after the FireFly phase). Pure plan in `src/core/paladin/bootstrap.py`: deploy, through node1's RPC and in the operator's order, `registry` (constructor `[false]`, key `registry.operator`), `noto`, `noto_factory`, then `noto_factory_proxy` (constructor: the factory address and the `initialize(noto)` call data, built purely from the Noto address). Save the four addresses in `deployed-addresses.json` (as `paladin-registry`, `paladin-noto`, `paladin-noto-factory`, `paladin-noto-factory-proxy`). Then write each node's runtime config with the Noto domain (`registryAddress` = the factory proxy) and the EVM registry (`contractAddress` = the registry), restart the three Paladin containers, and wait until each answers again and `domain_listDomains` returns `noto`. Re-running `deploy` skips what is done (contracts that still have code on chain; a config that already holds the addresses is not rewritten and the nodes are not restarted).

**Acceptance criteria:**
- [x] The four addresses are non-zero and have code on chain, deployed by Paladin's own keys (the integration test checks the deployer is node1's `registry.operator` key and that FireFly has no operation for them)
- [x] After `deploy`, `domain_listDomains` returns `noto` on all three nodes
- [x] A second `deploy` sends no Paladin transaction and does not restart the nodes (unit-tested on the pure plan and checked by the integration test through the nodes' start times)
- [x] An interrupted bootstrap (killed after some contracts) is finished by running `deploy` again

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k paladin_bootstrap`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 3, 4

**Files likely touched:**
- `src/core/paladin/bootstrap.py`, `src/core/paladin/config.py` (the config with domain and registry)
- `src/adapters/paladin_deploy.py`, `src/adapters/trex_command.py` or a new command module, `src/adapters/stack_cli.py`
- `tests/unit/core/test_paladin_bootstrap.py`, `tests/unit/adapters/test_paladin_deploy.py`, `tests/integration/test_paladin_bootstrap.py`

**Size:** M

**Status:** Done 2026-10-03. Test-first (11 pure tests for the bootstrap plan, 16 for the runner, 4 for the addresses file, CLI and `DockerStack.restart` tests; 8 new integration tests). `stack.py deploy` now runs a Paladin phase after the T-REX phase: the four contracts are deployed through node1 in the operator's order by Paladin's own keys (`registry.operator` and the others; the registry with `[false]`, the proxy with the factory and `initialize(noto)` call data), each address is saved as `paladin-registry`, `paladin-noto`, `paladin-noto-factory` and `paladin-noto-factory-proxy`, each node's config in `paladin-runtime/` is rebuilt as the committed base plus the Noto domain and EVM registry blocks, and a node is restarted only if its config changed or its domain is not loaded. **On the real stack it worked first time:** all three nodes list `noto`, a second `deploy` took 4 s, sent nothing and restarted no node, and a bootstrap killed after two contracts was finished by running the phase again without redeploying them. Runtime code sizes are checked on chain (all under 24,576). `deployed-addresses.json` is now written by merging (`src/adapters/addresses.py`), because the T-REX phase used to replace the whole file and would have erased the Paladin entries; it has 22 entries. Proof of who deployed: each contract's creation transaction on Besu is from the key node1 resolves for its label (`ptx_queryTransactionReceipts` gives the transaction hash), and FireFly has no deploy operation for them. A test-order issue showed up in the full run (`paladin_nodes` ran just after the interruption test had restarted the nodes and saw one `starting`); the interruption test now waits for a healthy stack before it ends. Full suite from a fresh `reset`, `up`, `deploy`: 79 passed plus that one, and the two modules re-run together passed (12).

### Task 6: Register the three nodes in the EVM registry

**Description:** As part of the Paladin phase of `deploy`, mirror the operator's flow: node1's `registry.operator` key calls `registerIdentity(parentIdentityHash = 0x00..00, name = nodeN, owner = nodeN's registry.nodeN key address)` for each node; then each node calls `setIdentityProperty(identityHash, "transport.grpc", <transport_localTransportDetails("grpc")>)` with its own `registry.nodeN` key. Pure code decides what is missing from `reg_queryEntries` (an identity not yet registered, a property not yet set), so a second run sends nothing.

**Acceptance criteria:**
- [x] `reg_queryEntries` on node1 lists `node1`, `node2` and `node3`, each with a `transport.grpc` property whose endpoint is `dns:///paladin-nodeN:9000`
- [x] A second run sends no registry transaction (the integration test counts the registry's logs on chain before and after)
- [x] The pure decision logic is unit-tested for nothing registered, some registered, everything registered, and a property already set

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k paladin_registry`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 5

**Files likely touched:**
- `src/core/paladin/registry.py`, `src/adapters/paladin_deploy.py`
- `tests/unit/core/test_paladin_registry.py`, `tests/integration/test_paladin_registry.py`

**Size:** S

**Status:** Done 2026-10-03. Test-first (7 pure tests for the decisions, 6 for the runner with a stateful fake of the registry, 2 for the wiring; 11 integration tests). Pure `src/core/paladin/registry.py` decides from `reg_queryEntriesWithProps` (which, unlike `reg_queryEntries`, shows each entry's `properties`) what is missing: every absent identity first, then every absent or outdated `transport.grpc`. `src/adapters/paladin_registry.py` sends `registerIdentity` from node1's `registry.operator` key with each node's own `registry.<node>` address as owner, then each node sets its own `transport.grpc` (the output of `transport_localTransportDetails`: `dns:///paladin-<node>:9000` plus its certificate) with its own key on its own node. It runs as the last step of the Paladin phase, after every domain is loaded. On the real stack it worked first time: node1 lists `node1`, `node2`, `node3` (and the `root` entry owned by `registry.operator`), all with their endpoints; a second `deploy` sent no registry transaction (the registry's logs on chain did not grow).

**Race found by the checkpoint run and fixed:** a cold `deploy` exited 1 with `KeyError: 'node3'` (the integration run still passed, because its `deployed` fixture ran `deploy` again). After a registration is mined, node1's block indexer shows the new entry a moment later, so reading the registry straight away missed the entry needed for the next step. The runner now polls (bounded, 60 s) until all three entries are visible, and reports `node1: not in the registry index ...` instead of a traceback. Two unit tests cover the delayed and the never-visible cases. Three consecutive cold `reset`, `up`, `deploy` cycles then all exited 0 (`up` 49 to 96 s, `deploy` 113 to 129 s, with Paladin). **Lesson for the checkpoints:** a fixture that re-runs `deploy` can hide a failing first `deploy`, so the checkpoint commands now also record the exit code of the first one.

## Checkpoint: After Tasks 3–6

- [x] `ruff check .`, `mypy .` and `pytest` clean (403 unit tests)
- [x] `python scripts/stack.py reset && up && deploy` leaves the Noto domain loaded on all three nodes and all three registered; a second `deploy` sends nothing (three cold cycles all exited 0; `pytest -m integration`: 91 passed in 10 min 40 s)
- [x] M3.1 gate from `docs/plan.md` (steps 1 and 2) holds
- [x] Anti-gate from `docs/plan.md` not triggered: Paladin runs from hand-written config on Compose
- [ ] Human review before proceeding (**waiting for Howin**)

---

## Group C — Noto (plan steps 3 to 5, DL-3.2, DL-3.3)

### Task 7: Deploy a Noto token and mint to Anson

**Description:** Pure request builders in `src/core/paladin/noto.py` for the three private calls (token deploy with `notary = notary@node1` and `notaryMode = "basic"`, `mint`, `balanceOf`), and an adapter function that deploys a token through node1 and mints 100 to `anson@node2` (submitted on node1). Without the constructor ABI Paladin fails with `PD200007: Parameter 'notary' is required`, so the deploy carries it (spike). The first call between nodes starts the gRPC connections, so this is where mutual TLS is exercised.

**Acceptance criteria:**
- [x] The token address is returned and is known to node1 (notary), node2 (Anson) and node3
- [x] `balanceOf` for `anson@node2`, asked of node2, returns 100 (`totalBalance`)
- [x] node1's log shows `TLS handshake completed` with node2 (and the client side on node2), proving mTLS between nodes
- [x] A second token can be deployed independently (each test deploys its own)

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k noto_mint`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 6

**Files likely touched:**
- `src/core/paladin/noto.py`, `src/adapters/paladin_noto.py`
- `tests/unit/core/test_noto.py`, `tests/integration/test_noto_mint.py`

**Size:** M

**Status:** done. 4 integration tests pass (71 s); node1 and node2 logs show `TLS handshake completed`.

### Task 8: Transfer from Anson to Beatrice

**Description:** `transfer` of 40 from `anson@node2` to `beatrice@node3`, submitted on node2 (Anson's own node), then balances read from each owner's node. This crosses all three nodes: Anson's coin is spent, the notary (node1) endorses, Beatrice's node receives her coin.

**Acceptance criteria:**
- [x] After minting 100 and transferring 40: `balanceOf` for `anson@node2` on node2 is 60 and for `beatrice@node3` on node3 is 40
- [x] The transfer is submitted on node2 and its receipt is a success
- [x] A transfer larger than the balance fails with Paladin's error and changes no balance

**Verification:**
- [x] Tests pass: `pytest -m integration -k noto_transfer`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 7

**Files likely touched:**
- `src/adapters/paladin_noto.py`
- `tests/integration/test_noto_transfer.py`

**Size:** S

**Status:** done. 2 integration tests pass (16 s). An oversize transfer fails with `PD012616: Domain reverted transaction on assemble: PD200005: Insufficient funds`; right after a mint Paladin once reported `available=200` for a 100 balance (message quirk only: a 150 transfer was still refused with `available=100` and the balance stayed 100).

### Task 9: Privacy: what each node can see, and what is on the public chain

**Description:** Prove the point of Noto. Pure code in `src/core/paladin/privacy.py` reads the coin states each node lists for a token (`pstate_queryContractStates`) and compares them with what each party should see. Two checks: **(a)** after the mint, node3 (not a party to it) sees no coin of this token; after the transfer node3 sees only its own coin (40), while node1 (notary) and node2 see 40, 60 and 100 as the spike measured. **(b)** The public chain: `eth_getLogs` for the token's address contain no plain 100, 40 or 60 in any 32-byte word of data or topics, and no wallet address of Anson or Beatrice.

**Acceptance criteria:**
- [x] node3 lists no coin right after the mint and exactly one (40) after the transfer
- [x] node1 and node2 list 40, 60 and 100 after the transfer
- [x] No log of the token on Besu contains the amounts or the party addresses
- [x] The comparison logic is unit-tested with canned coin lists, including a failing case that proves it can detect a leak

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k noto_privacy`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 8

**Files likely touched:**
- `src/core/paladin/privacy.py`, `src/adapters/paladin_noto.py`
- `tests/unit/core/test_privacy.py`, `tests/integration/test_noto_privacy.py`

**Size:** S

**Status:** done. 3 integration tests pass (72 s). Amounts are read from each state's `data.amount`; spent coins stay listed, which is why node1/node2 see 40, 60 and 100 and node3 only 40.

### Task 10: `stack.py noto-demo`

**Description:** A command that runs the whole story against the live stack and prints it: deploy a new Noto token with node1 as notary, mint 100 to Anson on node2, transfer 40 to Beatrice, print each party's balance and the coin amounts each node can see (the DL-3.2 and DL-3.3 demo, replacing the spike's `noto-3node.mjs` and `coins-by-node.mjs`). It creates a new token on every run. It stops with a clear message if the stack is not deployed.

**Acceptance criteria:**
- [x] On a deployed stack, `python scripts/stack.py noto-demo` exits 0 and prints Anson 60, Beatrice 40 and the per-node view
- [x] On a stack where `deploy` has not run, it exits 1 and says to run `deploy` first
- [x] The output is produced by `src/adapters`, not by `src/core`

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k noto_demo`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 9

**Files likely touched:**
- `src/adapters/stack_cli.py`, `src/adapters/paladin_noto.py`
- `tests/unit/adapters/test_stack_cli.py`, `tests/integration/test_noto_demo.py`

**Size:** S

**Status:** done. Real run exits 0 and prints Anson 60, Beatrice 40 and each node's view; with `deployed-addresses.json` moved away it exits 1 with "run `stack.py deploy` first" (checked by hand, plus unit tests).

## Checkpoint: After Tasks 7–10

- [x] `ruff check .`, `mypy .` and `pytest` clean (439 unit tests; `pytest -m integration`: 102 passed in 14 min 27 s)
- [x] Mint 100, transfer 40: Anson 60 on node2, Beatrice 40 on node3; node3 never sees the mint or Anson's change
- [x] The public chain data for the token shows no amounts and no party addresses
- [x] M3 gate steps 3 to 5 from `docs/plan.md` hold
- [ ] Human review before proceeding (**waiting for Howin**)

---

Note: a first full integration run was stopped by the tool's 30-minute background limit at about 70% (no failure shown); the rerun with a 2-hour limit passed 102/102. Cause of the slow first run is not known.

---

## Group D — Reset, restart and close-out (plan step 6)

### Task 11: Reset clears Paladin; a plain restart keeps it

**Description:** `python scripts/stack.py reset` already removes every container and volume of the Compose project and (since Task 2) the generated runtime config `paladin-runtime/`; extend it for the Paladin entries of `deployed-addresses.json`, and print what it removed. Prove two properties: after `reset` and `up`, Paladin starts clean against the fresh chain (no domain until `deploy`, no earlier token); and after a **plain restart** of the Paladin containers (no `down -v`), the nodes keep their keys and state: the same `registry.operator` and `registry.nodeN` addresses, the registered identities, and the balances of an earlier token (the key-derivation hazard from the spike).

**Acceptance criteria:**
- [x] After `reset` and `up`, no Paladin container, volume or `paladin-runtime/` folder from before remains, and the nodes report no domain
- [x] After `docker restart` of the three Paladin containers, `keymgr_resolveKey` for `registry.operator` and `registry.node1` returns the same address as before, `reg_queryEntries` still lists the three nodes, and the balance of an earlier token is unchanged
- [x] `reset` exits non-zero when Docker is not reachable, as before

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k paladin_reset`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 9

**Files likely touched:**
- `src/adapters/stack_cli.py`
- `tests/unit/adapters/test_stack_cli.py`, `tests/integration/test_paladin_reset.py`

**Size:** S

**Status:** done. `reset` already removed the whole `deployed-addresses.json` (all entries, Paladin included), so no code change was needed there; `test_reset` now also checks that every node has no domain after `reset` and `up`, and `test_paladin_reset` proves keys, registry and balances survive `docker restart` (47 s).

### Task 12: Repeatability and Phase 3 documentation

**Description:** Prove `reset && up && deploy` leaves a working Noto setup three times in a row with the full gate. Then update `README.md` (Getting started, Accessing, the Paladin ports and `noto-demo`), `PROJECT.md`, `docs/deliverables.md` (DL-3.1 to DL-3.3 with runnable examples, every one run against the live stack), `docs/plan.md` (Phase 3 status) and `docs/spike-results.md` (Phase 3 findings), and verify the README from a fresh clone.

**Acceptance criteria:**
- [ ] `reset && up && deploy` followed by `pytest -m integration` passes in three consecutive runs
- [ ] Following the README literally from a clean clone brings up the stack, deploys COIN and the Noto setup, and the gate passes
- [ ] `docs/deliverables.md` DL-3.1 to DL-3.3 are `Done` with commands that were actually run, and `docs/plan.md` marks Phase 3 with the date and the exact result

**Verification:**
- [ ] Tests pass: `pytest` and the gate, three times
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 1–11

**Files likely touched:**
- `README.md`, `PROJECT.md`, `docs/deliverables.md`, `docs/plan.md`, `docs/spike-results.md`

**Size:** S

## Checkpoint: After Tasks 11–12 (Phase 3 exit gate)

- [ ] Noto integration tests pass (mint, transfer, privacy, restart)
- [ ] `python scripts/stack.py reset` clears all three stores (chain, FireFly DB, Paladin DB)
- [ ] The gate passes three times in a row from `reset`, `up` and `deploy`
- [ ] `ruff check .`, `mypy .` and `pytest` clean
- [ ] Anti-gate from `docs/plan.md`: if Paladin cannot run from hand-written config on Compose, fall back to Paladin on `kind` and record the change in D-09 (not expected, the spike ran it)
- [ ] Human review before proceeding

---

## Open Questions

| # | Question | Owner | Needed by | Decision (all as recommended, Howin 2026-10-03) |
|---|----------|-------|-----------|----------------|
| 1 | Which Besu RPC node does each Paladin node use? | Howin | Task 2 | **Answered by the move to one RPC node (plan D-17, 2026-10-03): all three use `besu-rpc-anson`** |
| 2 | The registry and Noto contract artifacts and the private Noto ABI are not in the image; they are Apache-2.0 release assets (~95 KB). Vendor them, or download them at `deploy` time? | Howin | Task 3 | **Vendor them unchanged under `contracts/paladin/`** with source URLs and SHA-256, so a fresh clone works offline and the exact bytes are pinned. (T-REX is different: it is installed with `npm ci` because it is GPL and large) |
| 3 | TLS certificates: generate with `openssl` inside the Paladin image (same Docker pattern as the Besu generator), or add the `cryptography` Python dependency? | Howin | Task 1 | **`openssl` in the image**: no new dependency (CLAUDE.md §12), and it is the tool the spike used |
| 4 | Two-phase config: the nodes start with a base config, and `deploy` writes the final one (with the domain and registry addresses). Keep the base config committed in `network-config/paladin/` and the final config in a gitignored `paladin-runtime/` folder that Compose mounts, seeded by `up` when missing? | Howin | Task 2 | **Yes.** The addresses only exist after `deploy`, so the final config cannot be committed, and `up` must still work on a fresh clone |
| 5 | Mnemonics: generate with `eth-account`'s HD wallet support (already a dependency) and commit them as demo keys (D-10)? | Howin | Task 1 | **Yes**, like the wallets |
| 6 | Which Paladin ports to publish? The spike published HTTP and WS RPC for each node | Howin | Task 2 | **HTTP RPC only: `8548`, `8648`, `8748`** (WS is not needed by this project; fewer open ports) |
| 7 | Paladin log level: the spike used `debug` | Howin | Task 2 | **`info`**: `debug` is very noisy and slows three JVMs; raise it when debugging |
| 8 | `noto-demo` creates a new token on every run and prints the story. Is that the right shape for the DL-3.2 "script"? | Howin | Task 10 | **Yes**, as a `stack.py` subcommand rather than a separate script, in line with D-16 |
| 9 | Noto notary mode: `basic` (spike) or `hooks`? | Howin | Task 7 | **`basic`** (the notary endorses without custom hooks; `hooks` is out of scope) |

## Notes for review

- No task is sized L or larger. M: Tasks 1, 2, 5 (and 7). S: Tasks 3, 4, 6, 8, 9, 10, 11, 12.
- No verification command is `TBD`; all come from `PROJECT.md`. The `noto-demo` subcommand and the Paladin phase of `deploy` are created in Tasks 10 and 5.
- **Highest risk is early:** Task 5 (the two-phase bootstrap with a restart) and Task 2 (three JVMs more on a machine that already struggles with load). The spike proved the bootstrap on one chain, so the unknowns are our wiring and start-up time. If four more containers make the fault-injection tests (already excluded from the gate) or `up` markedly worse, we record it at the first checkpoint.
- One thing to confirm in Task 2: which Paladin RPC call shows that a node is connected to Besu and indexing blocks (the spike saw it in the node's logs).
- Out of scope for Phase 3: Zeto, Pente, ERC-3643 inside Pente, the CLI and Caliper (plan §4 Phase 3 "Out of scope").
- Phase 3 is about 4 to 6 days (plan).
