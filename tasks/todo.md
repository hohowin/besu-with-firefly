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
- [ ] `ruff check .`, `mypy .` and `pytest` all pass on a smoke test, with mypy in strict mode and no lint rule disabled to make them pass
- [ ] `pytest -m integration` selects zero tests without error, and plain `pytest` does not run integration tests
- [ ] `PROJECT.md` Commands lists install, lint, type-check, unit test and integration test commands, and Directory Layout matches the real folders

**Verification:**
- [ ] Tests pass: `pytest`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** None

**Files likely touched:**
- `pyproject.toml`
- `src/core/__init__.py`, `src/adapters/__init__.py`
- `tests/unit/test_smoke.py`
- `PROJECT.md`
- `.gitignore`

**Size:** M

### Task 2: Pure QBFT genesis builder

**Description:** In `src/core/network/`, add a pure function that builds the input for `besu operator generate-blockchain-config` from parameters (chainId, block period, request timeout, fork settings, validator count). The output is a plain dict equal to the spike's `qbft-config.json`: `berlinBlock 0`, `londonBlock 0`, `zeroBaseFee true`, `shanghaiTime 0`, the `qbft` block, `alloc {}`, `blockchain.nodes.generate true` and `count`. It validates inputs (count at least 4 for `f=1`, positive timing values). No file or Docker access.

**Acceptance criteria:**
- [ ] With the project defaults, the result equals the spike's `spike/qbft/qbft-config.json` except `count` 4
- [ ] A validator count below 4 raises a clear error that names the `n = 3f + 1` rule
- [ ] The module has no imports of `os`, `subprocess`, `pathlib` I/O calls or `print`

**Verification:**
- [ ] Tests pass: `pytest tests/unit/core/test_genesis.py`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 1

**Files likely touched:**
- `src/core/network/genesis.py`
- `tests/unit/core/test_genesis.py`

**Size:** S

### Task 3: Pure enode and static-nodes builder

**Description:** In `src/core/network/`, add pure functions that turn a validator public key (128 hex characters, with or without `0x`) plus an IP and port into `enode://PUBKEY@IP:30303`, and build the `static-nodes.json` list from the four validators with their fixed IPs. The subnet and per-node IPs come from a small configuration value object (default subnet `172.28.0.0/16`, validators `.11` to `.14`, RPC nodes `.21` and `.22`).

**Acceptance criteria:**
- [ ] A known public key and IP produce the exact expected enode string
- [ ] A public key that is not 128 hex characters raises a clear error
- [ ] The validator and RPC addresses are all inside the configured subnet and unique, checked by a unit test

**Verification:**
- [ ] Tests pass: `pytest tests/unit/core/test_enode.py`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 1

**Files likely touched:**
- `src/core/network/enode.py`
- `tests/unit/core/test_enode.py`

**Size:** S

### Task 4: `stack.py init` generates genesis, validator keys and static nodes

**Description:** Add `python scripts/stack.py init`, backed by an adapter in `src/adapters/`. It builds the config with Task 2, runs `besu operator generate-blockchain-config` in the pinned Besu image through Docker, and writes `network-config/genesis.json`, `network-config/validator-keys/validator-1..4/` (`key`, `key.pub`, `address.txt`, ordered by sorted address so the mapping is stable) and `network-config/static-nodes.json` (Task 3). It ignores the harmless `Output directory already exists` message but checks that the files really exist, and it refuses to overwrite existing files unless `--force` is given. Demo keys are committed (D-10); add a short `network-config/README.md` marking them demo-only.

**Acceptance criteria:**
- [ ] After `init`, `genesis.json` has a `qbft` block, `chainId` 20260916, `zeroBaseFee true`, and `extraData` containing all four validator addresses from `address.txt`
- [ ] `static-nodes.json` lists four enodes whose public keys match the four `key.pub` files
- [ ] Running `init` a second time without `--force` fails with a clear message and changes nothing; with `--force` it regenerates

**Verification:**
- [ ] Tests pass: `pytest tests/unit` and `pytest -m integration -k init` (the integration test runs the real Besu image)
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 2, 3

**Files likely touched:**
- `scripts/stack.py`
- `src/adapters/besu_config.py`
- `network-config/` (generated, committed)
- `network-config/README.md`
- `tests/integration/test_init.py`

**Size:** M

### Task 5: Demo wallet keys

**Description:** Extend `init` to generate the `admin`, `anson` and `beatrice` demo wallets and write them to `network-config/wallets.json` (name, address, private key) with a demo-only banner. FireFly keystores come later (Phase 2). The secp256k1 library choice is an Open Question.

**Acceptance criteria:**
- [ ] `wallets.json` has three entries, each address derived from its private key, and a test re-derives every address
- [ ] The file is committed, and `network-config/README.md` states that these keys are demo-only (D-10)
- [ ] Re-running `init` without `--force` leaves the wallets unchanged

**Verification:**
- [ ] Tests pass: `pytest tests/unit` and `pytest -m integration -k init`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 4, and an answer to Open Question 3

**Files likely touched:**
- `src/core/network/wallets.py` (pure address derivation check)
- `src/adapters/besu_config.py`
- `network-config/wallets.json`
- `tests/unit/core/test_wallets.py`

**Size:** S

## Checkpoint: After Tasks 1–5

- [ ] `ruff check .`, `mypy .` and `pytest` are clean
- [ ] `python scripts/stack.py init --force` reproduces valid genesis, keys, static nodes and wallets from scratch
- [ ] M1.1 exit gate from `docs/plan.md` holds: `genesis.json` has a `qbft` block with all four validator addresses
- [ ] Human review before proceeding

---

## Group B — Validators (M1.2)

### Task 6: Four validators run and produce blocks

**Description:** Write `docker-compose.yml` with `besu-validator-1..4` on a bridge network with fixed IPs (the subnet from Task 3), each mounting the shared genesis, its own key as `--node-private-key-file`, and `static-nodes.json` in its data path. Flags follow `docs/spike-results.md`: `--min-gas-price=0`, `--host-allowlist=*`, `--p2p-host=0.0.0.0`, no published ports. Add `python scripts/stack.py up`, which runs `docker compose up -d` and waits until the containers are healthy.

**Acceptance criteria:**
- [ ] `docker compose config` exits 0, and `python scripts/stack.py up` brings all four validators to `healthy` with no restart loop
- [ ] Each validator log shows at least 3 peers, and `Produced #N` lines appear every ~2 seconds
- [ ] The chosen subnet does not collide with an existing Docker network on this machine (checked at the start of the task)

**Verification:**
- [ ] Tests pass: `pytest -m integration -k validators` (the test reads container health and logs through the Docker CLI)
- [ ] Checks clean: `docker compose config`, `ruff check .`, `mypy .`

**Dependencies:** Task 4

**Files likely touched:**
- `docker-compose.yml`
- `scripts/stack.py`
- `src/adapters/docker_stack.py`
- `tests/integration/test_validators.py`

**Size:** M

### Task 7: One validator can fail without halting the chain

**Description:** Prove `f=1` using the validators only: stop one validator, check that block production continues in the others' logs within 30 seconds, restart it, and check that it rejoins. Wrap this as an integration test so it stays proven. Also stop a second validator once and record that the chain halts, to document risk R10 (accepted, not a defect).

**Acceptance criteria:**
- [ ] With `besu-validator-4` stopped, a new `Produced #` line appears on another validator within 30 seconds
- [ ] After `docker start besu-validator-4`, its log shows it syncing and peering again
- [ ] With two validators stopped, no new block appears within 30 seconds (documented as R10); the test restores the stack afterwards

**Verification:**
- [ ] Tests pass: `pytest -m integration -k fault`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 6

**Files likely touched:**
- `tests/integration/test_fault_tolerance.py`
- `src/adapters/docker_stack.py`

**Size:** S

## Checkpoint: After Tasks 6–7

- [ ] All four validators healthy, peered and producing blocks
- [ ] Killing any single validator does not halt block production (M1.2 exit gate)
- [ ] Anti-gate from `docs/plan.md`: if one failed validator halts the chain, stop and re-check `extraData` against the validator keys
- [ ] Human review before proceeding

---

## Group C — RPC nodes (M1.3)

### Task 8: Two RPC nodes join and agree

**Description:** Add `besu-rpc-anson` (`8545` HTTP, `8546` WS) and `besu-rpc-beatrice` (`8555` HTTP, `8556` WS) to the Compose file as non-validating nodes (no `--node-private-key-file`), statically peered to the four validators, with HTTP and WS RPC enabled and the `ETH,NET,WEB3,QBFT,ADMIN` APIs. Extend `stack.py up` to wait for both.

**Acceptance criteria:**
- [ ] `eth_blockNumber` on `:8545` and `:8555` agree within 1 block when read 5 seconds apart
- [ ] `eth_gasPrice` returns `0x0` on both
- [ ] Neither RPC node's address is in `qbft_getValidatorsByBlockNumber`, and each reports at least 4 peers (`net_peerCount`)

**Verification:**
- [ ] Tests pass: `pytest -m integration -k rpc`
- [ ] Checks clean: `docker compose config`, `ruff check .`, `mypy .`

**Dependencies:** Task 6

**Files likely touched:**
- `docker-compose.yml`
- `scripts/stack.py`
- `tests/integration/test_rpc_nodes.py`
- `tests/support/rpc.py` (a small JSON-RPC helper using the standard library)

**Size:** M

### Task 9: Network integration suite

**Description:** Consolidate the network proofs into one stable suite that uses the RPC nodes: RPC consistency, zero gas price, the validator set is exactly the four expected addresses, and fault tolerance re-proved through block numbers (stop a validator, `eth_blockNumber` still increases within 30 seconds on both RPC nodes). Replace log-based checks from Task 7 where RPC is now available, and keep the log-based "two validators down halts" check.

**Acceptance criteria:**
- [ ] `pytest -m integration` passes against a freshly started stack
- [ ] The fault-tolerance test restores the stopped validator even when an assertion fails
- [ ] Tests wait with bounded polling instead of fixed sleeps, and fail with a message naming the node and the observed value

**Verification:**
- [ ] Tests pass: `pytest -m integration`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 7, 8

**Files likely touched:**
- `tests/integration/test_network.py`
- `tests/support/rpc.py`
- `tests/integration/conftest.py`

**Size:** M

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
