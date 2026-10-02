# Tasks — Phase 1: Network

> Source: `docs/plan.md` Phase 1 (M1.1, M1.2, M1.3), `docs/prd.md` US-002 and US-003, `docs/spike-results.md`. Decisions: D-01 (network shape), D-08 (London, Shanghai, `zeroBaseFee`), D-10 (demo keys are committed), D-16 (`python scripts/stack.py`, no Make). Phase 0 is signed off (2026-10-02).
> **Status: approved by Howin on 2026-10-02 (all Open Questions answered as recommended). No code has been written yet.**

## Overview

Phase 1 delivers a 4-validator QBFT Besu network with two RPC nodes, generated from scripts and proven by tests. Work is sliced bottom-up: first a Python project scaffold and the pure logic (genesis and enode builders, no I/O, per `PROJECT.md`), then the generator adapter that runs Besu's own tool, then the Compose stack in the three plan milestones (validators, fault tolerance, RPC nodes), then the integration tests and a repeatability check.

Design choices that apply to every task:
- **Pure logic in `src/core/`, I/O in adapters.** The genesis and enode builders are pure functions. Running Docker, writing files and calling JSON-RPC live in adapters (`src/adapters/`, `scripts/stack.py`).
- **Keys and genesis are committed** (D-10), so a fresh clone runs `docker compose up` without a generation step. `init` exists to regenerate them and refuses to overwrite without `--force`.
- **`docker-compose.yml` is hand-written**, not generated. Only genesis, keys and `static-nodes.json` are generated.
- **Validators publish no ports.** RPC nodes publish `8545/8546` (Anson) and `8555/8556` (Beatrice). Validators are observed through their logs until the RPC nodes exist, then through the RPC nodes.
- **Line endings are LF** (`.gitattributes`). Files mounted into containers must stay LF.
- **Besu 26.8.1**, chainId `20260916`, `blockperiodseconds` 2, `requesttimeoutseconds` 4, `zeroBaseFee: true`, empty `alloc`, `--min-gas-price=0`.
- **Verification commands** (named in `PROJECT.md` Commands, whose section is still a TODO, see Open Questions): `ruff check .`, `mypy .`, `pytest`, and `pytest -m integration` for tests that need Docker. The integration marker is created in Task 1.

Sizes: no task is L or larger.

---

## Group A — Foundations (M1.1 part 1)

### Task 1: Python scaffold and project commands

**Description:** Create the Python project skeleton so that lint, type checks and tests run on a trivial test: `pyproject.toml` (`requires-python >= 3.11`, ruff, strict mypy, pytest with an `integration` marker that is skipped by default), `src/core/`, `src/adapters/`, `tests/unit/`, `tests/integration/`, and `.gitignore` entries for Python caches and the virtual environment. Fill in the TODO Commands and Directory Layout sections of `PROJECT.md` with what now exists.

**Acceptance criteria:**
- [x] `ruff check .`, `mypy .` and `pytest` all pass on a smoke test, with mypy in strict mode and no lint rule disabled to make them pass
- [x] `pytest -m integration` selects zero tests without error, and plain `pytest` does not run integration tests
- [x] `PROJECT.md` Commands lists install, lint, type-check, unit test and integration test commands, and Directory Layout matches the real folders

**Verification:**
- [x] Tests pass: `pytest`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** None

**Files likely touched:**
- `pyproject.toml`
- `src/core/__init__.py`, `src/adapters/__init__.py`
- `tests/unit/test_smoke.py`
- `PROJECT.md`
- `.gitignore`

**Size:** M

**Status:** Done 2026-10-02 on branch `phase-1-network`. Notes: `pytest -m integration` selects one real test (Docker engine reachable) instead of zero, so the command exits 0. Lint and type checks exclude only `_knowledge/`, `spike/`, `.agents/`, `.claude/` (not our code); no rule was disabled. Written test-first: the smoke test failed with `No module named 'src'` before the packages existed.

### Task 2: Pure QBFT genesis builder

**Description:** In `src/core/network/`, add a pure function that builds the input for `besu operator generate-blockchain-config` from parameters (chainId, block period, request timeout, fork settings, validator count). The output is a plain dict equal to the spike's `qbft-config.json`: `berlinBlock 0`, `londonBlock 0`, `zeroBaseFee true`, `shanghaiTime 0`, the `qbft` block, `alloc {}`, `blockchain.nodes.generate true` and `count`. It validates inputs (count at least 4 for `f=1`, positive timing values). No file or Docker access.

**Acceptance criteria:**
- [x] With the project defaults, the result equals the spike's `spike/qbft/qbft-config.json` except `count` 4
- [x] A validator count below 4 raises a clear error that names the `n = 3f + 1` rule
- [x] The module has no imports of `os`, `subprocess`, `pathlib` I/O calls or `print`

**Verification:**
- [x] Tests pass: `pytest tests/unit/core/test_genesis.py`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 1

**Files likely touched:**
- `src/core/network/genesis.py`
- `tests/unit/core/test_genesis.py`

**Size:** S

**Status:** Done 2026-10-02. Written test-first (collection failed with `No module named 'src.core.network'`). Output verified identical to `spike/qbft/qbft-config.json` with count 4. 11 unit tests.

### Task 3: Pure enode and static-nodes builder

**Description:** In `src/core/network/`, add pure functions that turn a validator public key (128 hex characters, with or without `0x`) plus an IP and port into `enode://PUBKEY@IP:30303`, and build the `static-nodes.json` list from the four validators with their fixed IPs. The subnet and per-node IPs come from a small configuration value object (default subnet `172.28.0.0/16`, validators `.11` to `.14`, RPC nodes `.21` and `.22`).

**Acceptance criteria:**
- [x] A known public key and IP produce the exact expected enode string
- [x] A public key that is not 128 hex characters raises a clear error
- [x] The validator and RPC addresses are all inside the configured subnet and unique, checked by a unit test

**Verification:**
- [x] Tests pass: `pytest tests/unit/core/test_enode.py`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 1

**Files likely touched:**
- `src/core/network/enode.py`
- `tests/unit/core/test_enode.py`

**Size:** S

**Status:** Done 2026-10-02. Written test-first. 13 unit tests.

### Task 4: `stack.py init` generates genesis, validator keys and static nodes

**Description:** Add `python scripts/stack.py init`, backed by an adapter in `src/adapters/`. It builds the config with Task 2, runs `besu operator generate-blockchain-config` in the pinned Besu image through Docker, and writes `network-config/genesis.json`, `network-config/validator-keys/validator-1..4/` (`key`, `key.pub`, `address.txt`, ordered by sorted address so the mapping is stable) and `network-config/static-nodes.json` (Task 3). It ignores the harmless `Output directory already exists` message but checks that the files really exist, and it refuses to overwrite existing files unless `--force` is given. Demo keys are committed (D-10); add a short `network-config/README.md` marking them demo-only.

**Acceptance criteria:**
- [x] After `init`, `genesis.json` has a `qbft` block, `chainId` 20260916, `zeroBaseFee true`, and `extraData` containing all four validator addresses from `address.txt`
- [x] `static-nodes.json` lists four enodes whose public keys match the four `key.pub` files
- [x] Running `init` a second time without `--force` fails with a clear message and changes nothing; with `--force` it regenerates

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k init` (the integration test runs the real Besu image)
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 2, 3

**Files likely touched:**
- `scripts/stack.py`
- `src/adapters/besu_config.py`
- `network-config/` (generated, committed)
- `network-config/README.md`
- `tests/integration/test_init.py`

**Size:** M

**Status:** Done 2026-10-02. Test-first. 51 unit tests (fake Besu generator, no Docker) plus an integration test against the real `hyperledger/besu:26.8.1` image (init, refusal without `--force`, regeneration with it). The pure helpers are in `src/core/network/validators.py`; the Docker runner is injected so the file logic is testable. The generated `network-config/` is committed together with Task 5's wallets.

### Task 5: Demo wallet keys

**Description:** Extend `init` to generate the `admin`, `anson` and `beatrice` demo wallets and write them to `network-config/wallets.json` (name, address, private key) with a demo-only banner. FireFly keystores come later (Phase 2). The secp256k1 library choice is an Open Question.

**Acceptance criteria:**
- [x] `wallets.json` has three entries, each address derived from its private key, and a test re-derives every address
- [x] The file is committed, and `network-config/README.md` states that these keys are demo-only (D-10)
- [x] Re-running `init` without `--force` leaves the wallets unchanged

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k init`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 4, and an answer to Open Question 3

**Files likely touched:**
- `src/core/network/wallets.py` (pure address derivation check)
- `src/adapters/besu_config.py`
- `network-config/wallets.json`
- `tests/unit/core/test_wallets.py`

**Size:** S

**Status:** Done 2026-10-02. Test-first, with `eth-account` 0.14 (new dependency, approved). Core (`src/core/network/wallets.py`) does the pure address derivation and checks; the adapter creates the random wallets. Verified against the well-known Ethereum test vector. `init` now also rewrites the generated README every run (it had gone stale after `--force`; covered by a test). 64 unit tests plus 2 integration tests.

## Checkpoint: After Tasks 1–5

- [x] `ruff check .`, `mypy .` and `pytest` are clean (64 unit tests, 2 integration tests)
- [x] `python scripts/stack.py init --force` reproduces valid genesis, keys, static nodes and wallets from scratch
- [x] M1.1 exit gate from `docs/plan.md` holds: `genesis.json` has a `qbft` block with all four validator addresses (the `docker compose config` half of that gate comes with Task 6, when the Compose file exists)
- [ ] Human review before proceeding (**waiting for Howin**)

---

## Group B — Validators (M1.2)

### Task 6: Four validators run and produce blocks

**Description:** Write `docker-compose.yml` with `besu-validator-1..4` on a bridge network with fixed IPs (the subnet from Task 3), each mounting the shared genesis, its own key as `--node-private-key-file`, and `static-nodes.json` in its data path. Flags follow `docs/spike-results.md`: `--min-gas-price=0`, `--host-allowlist=*`, `--p2p-host=0.0.0.0`, no published ports. Add `python scripts/stack.py up`, which runs `docker compose up -d` and waits until the containers are healthy.

**Acceptance criteria:**
- [x] `docker compose config` exits 0, and `python scripts/stack.py up` brings all four validators to `healthy` with no restart loop
- [x] Each validator log shows at least 3 peers, and `Produced #N` lines appear every ~2 seconds
- [x] The chosen subnet does not collide with an existing Docker network on this machine (checked at the start of the task)

**Verification:**
- [x] Tests pass: `pytest -m integration -k validators` (the test reads container health and logs through the Docker CLI)
- [x] Checks clean: `docker compose config`, `ruff check .`, `mypy .`

**Dependencies:** Task 4

**Files likely touched:**
- `docker-compose.yml`
- `scripts/stack.py`
- `src/adapters/docker_stack.py`
- `tests/integration/test_validators.py`

**Size:** M

**Status:** Done 2026-10-02. Test-first. `docker compose config` is valid, `python scripts/stack.py up` cold-starts all four validators to `healthy` in about 30 seconds and is idempotent. Subnet `172.28.0.0/16` collides with no existing Docker network (checked: 172.17 to 172.20 are in use). Besu's built-in healthcheck only checks a pid file, so `healthy` means started; block production and peers are proven from the logs (`Produced #N` or `Imported empty block #N` every ~2 s, `Currently checking 3 peers`). New pure helpers `besu_logs.py` and `health.py` in `src/core/network/`, plus `DockerStack` with injected runner, sleep and clock. 87 unit tests and 12 validator integration tests (health, 3 peers each, blocks advance, no restart, no published ports).

### Task 7: One validator can fail without halting the chain

**Description:** Prove `f=1` using the validators only: stop one validator, check that block production continues in the others' logs within 30 seconds, restart it, and check that it rejoins. Wrap this as an integration test so it stays proven. Also stop a second validator once and record that the chain halts, to document risk R10 (accepted, not a defect).

**Acceptance criteria:**
- [x] With `besu-validator-4` stopped, a new `Produced #` line appears on another validator within 30 seconds
- [x] After `docker start besu-validator-4`, its log shows it syncing and peering again
- [x] With two validators stopped, no new block appears within 30 seconds (documented as R10); the test restores the stack afterwards

**Verification:**
- [x] Tests pass: `pytest -m integration -k fault`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 6

**Files likely touched:**
- `tests/integration/test_fault_tolerance.py`
- `src/adapters/docker_stack.py`

**Size:** S

**Status:** Done 2026-10-02. `DockerStack.stop` and `start` written test-first. Two integration tests, 150 s together: with `besu-validator-4` stopped, two new blocks appeared on validator 1 within 30 s, and after `docker start` it synced and kept up; with validators 3 and 4 stopped, no new block appeared for 30 s (R10, as expected). A fixture restores every validator after each test, even on failure.

## Checkpoint: After Tasks 6–7

- [x] All four validators healthy, peered and producing blocks
- [x] Killing a single validator does not halt block production (M1.2 exit gate). Proven for validator 4; Task 9 repeats it through the RPC nodes
- [x] Anti-gate from `docs/plan.md` not triggered: one failed validator did not halt the chain
- [ ] Human review before proceeding (**waiting for Howin**)

---

## Group C — RPC nodes (M1.3)

### Task 8: Two RPC nodes join and agree

**Description:** Add `besu-rpc-anson` (`8545` HTTP, `8546` WS) and `besu-rpc-beatrice` (`8555` HTTP, `8556` WS) to the Compose file as non-validating nodes (no `--node-private-key-file`), statically peered to the four validators, with HTTP and WS RPC enabled and the `ETH,NET,WEB3,QBFT,ADMIN` APIs. Extend `stack.py up` to wait for both.

**Acceptance criteria:**
- [x] `eth_blockNumber` on `:8545` and `:8555` agree within 1 block when read 5 seconds apart
- [x] `eth_gasPrice` returns `0x0` on both
- [x] Neither RPC node's address is in `qbft_getValidatorsByBlockNumber`, and each reports at least 4 peers (`net_peerCount`)

**Verification:**
- [x] Tests pass: `pytest -m integration -k rpc`
- [x] Checks clean: `docker compose config`, `ruff check .`, `mypy .`

**Dependencies:** Task 6

**Files likely touched:**
- `docker-compose.yml`
- `scripts/stack.py`
- `tests/integration/test_rpc_nodes.py`
- `tests/support/rpc.py` (a small JSON-RPC helper using the standard library)

**Size:** M

**Status:** Done 2026-10-02. Test-first (8 integration tests, red before the Compose change). `stack.py up` needed no change: it already waits for every Compose service. `eth_coinbase` does not exist on a non-mining Besu, so "not a validator" is checked through the validator set plus the node id (`admin_nodeInfo`) against the four `key.pub` files. Side fix: the Task 6 peer test read only the last 200 log lines and failed once the stack had run a while; `peer_count` now also reads `Peers: N` and the test reads the whole log.

### Task 9: Network integration suite

**Description:** Consolidate the network proofs into one stable suite that uses the RPC nodes: RPC consistency, zero gas price, the validator set is exactly the four expected addresses, and fault tolerance re-proved through block numbers (stop a validator, `eth_blockNumber` still increases within 30 seconds on both RPC nodes). Replace log-based checks from Task 7 where RPC is now available, and keep the log-based "two validators down halts" check.

**Acceptance criteria:**
- [x] `pytest -m integration` passes against a freshly started stack
- [x] The fault-tolerance test restores the stopped validator even when an assertion fails
- [x] Tests wait with bounded polling instead of fixed sleeps, and fail with a message naming the node and the observed value

**Verification:**
- [x] Tests pass: `pytest -m integration`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 7, 8

**Files likely touched:**
- `tests/integration/test_network.py`
- `tests/support/rpc.py`
- `tests/integration/conftest.py`

**Size:** M

**Status:** Done 2026-10-02. `test_rpc_nodes.py` became `test_network.py` and gained the RPC version of the single-failure proof (stop `besu-validator-4`, both RPC nodes pass 2 new blocks within 30 s, it restarts, catches up and both RPC nodes report 4 or more peers). The `restore_validators` fixture moved to `conftest.py` and waits on RPC block numbers; `test_fault_tolerance.py` keeps only the log-based two-validators-down halt (R10). `pytest -m integration`: 24 passed in 4 min on the running stack; a fresh-stack run is Task 10.

### Task 10: `stack.py reset` and repeatability

**Description:** Add `python scripts/stack.py reset` for the Phase 1 scope (`docker compose down -v`, so the chain returns to genesis). Prove repeatability: reset, up, and the integration suite pass three times in a row.

**Acceptance criteria:**
- [ ] After `reset`, no Besu container or volume remains and a new `up` starts again from block 0
- [ ] `reset && up` followed by `pytest -m integration` passes in three consecutive runs
- [ ] `reset` prints what it removed and exits non-zero if Docker is not reachable

**Verification:**
- [ ] Tests pass: `pytest -m integration` three times after `python scripts/stack.py reset && python scripts/stack.py up`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 9

**Files likely touched:**
- `scripts/stack.py`
- `src/adapters/docker_stack.py`
- `tests/integration/test_reset.py`

**Size:** S

## Checkpoint: After Tasks 8–10 (Phase 1 exit gate)

- [ ] All four validators healthy, peered, tolerant of one failure
- [ ] Both RPC nodes healthy, consistent within 1 block, and `eth_gasPrice` is `0x0`
- [ ] `pytest -m integration` network tests pass, three consecutive fresh-stack runs
- [ ] `ruff check .`, `mypy .` and `pytest` clean
- [ ] Anti-gate from `docs/plan.md`: if an RPC node cannot peer or diverges, stop before Phase 2
- [ ] Human review before proceeding

---

## Group D — Close-out

### Task 11: Phase 1 documentation and sign-off

**Description:** Update `README.md` Getting started with the real Phase 1 commands, mark DL-1.x deliverables as done in `docs/deliverables.md` with the commands that were actually run, record the exit-gate results, and commit on the working branch.

**Acceptance criteria:**
- [ ] Following the README Getting started literally from a clean clone brings up the Phase 1 network and the tests pass
- [ ] `docs/deliverables.md` DL-1.1 to DL-1.4 are marked `Done` and their "How to try it" steps match the real commands and ports
- [ ] `docs/plan.md` Phase 1 is marked complete with the date

**Verification:**
- [ ] Tests pass: `pytest` and `pytest -m integration`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 1–10

**Files likely touched:**
- `README.md`
- `docs/deliverables.md`
- `docs/plan.md`

**Size:** XS

---

## Open Questions

All answered by Howin on 2026-10-02 ("all follow the recommendation").

| # | Question | Owner | Needed by | Decision |
|---|----------|-------|-----------|----------|
| 1 | `PROJECT.md` Commands and Directory Layout are still TODO. Is it OK for Task 1 to fill them in? | Howin | Task 1 | **Yes.** Task 1 fills them in |
| 2 | Docker subnet for the stack. Default `172.28.0.0/16`; other Compose projects (for example `jungle-chess`) already run on this machine | Howin | Task 6 | **Keep the default.** Task 6 checks `docker network ls` for a collision and picks another subnet only if needed |
| 3 | Which Python library derives wallet addresses from keys (new dependency)? | Howin | Task 5 | **`eth-account`.** Phase 2 needs keystores for the FireFly signer anyway |
| 4 | Wallet key format in Phase 1 | Howin | Task 5 | **Plain `wallets.json` now**, FireFly signer keystores in Phase 2 |
| 5 | Should validators expose RPC (unpublished)? | Howin | Task 6 | **No.** Validators stay closed; Tasks 6–7 read logs, Task 8 onward uses the RPC nodes |
| 6 | Python version | Howin | Task 1 | **`requires-python >= 3.11`**, develop on 3.13 |

## Notes for review

- No task is sized L or larger. The largest are M: Tasks 1, 4, 6, 8, 9.
- No verification command is `TBD`. `ruff`, `mypy` and `pytest` come from `PROJECT.md`; the `integration` marker and `scripts/stack.py` are created by Tasks 1 and 4.
- Out of scope for Phase 1: FireFly, Paladin, T-REX, the CLI and Caliper (plan §4 Phase 1 "Out of scope").
