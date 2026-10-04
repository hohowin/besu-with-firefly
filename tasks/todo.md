# Tasks — Phase 5: Caliper

> Source: `docs/plan.md` Phase 5 (steps 1 to 5, exit gate, anti-gate), `docs/prd.md` US-012 and FR-13, `docs/deliverables.md` DL-5.1 to DL-5.3, `docs/use-cases.md` UC-10, `docs/spike-results.md` (Risk 5 and "Versions to pin"), and the working spike in `spike/caliper/`. Decisions: D-14 (Caliper 0.6.0, direct RPC over `ws://`, a custom FireFly connector, `perf/` a separate Node sub-project, `web3@1.3.0` installed by hand, a setup step that creates N verified wallets), D-16 (`python scripts/stack.py`), D-17 (one validator, one RPC node). Phases 1 to 4 are complete; their lists are `tasks/phase-1-network.md`, `tasks/phase-2-firefly.md`, `tasks/phase-3-paladin.md` and `tasks/phase-4-cli.md` (Phase 4 was archived on 2026-10-04 with its "human review" box still open, at Howin's choice).
> **Status: draft, waiting for Howin's approval. No implementation has started.**

## Overview

Phase 5 measures the same `COIN` `transfer` at two layers on the running stack: sent straight to Besu over JSON-RPC (chain layer), and sent through FireFly's contract API (FireFly layer). It ends with a results note that states both sets of numbers, the difference, and the configuration they were measured under. The spike already proved the method on a toy contract with one key (`spike/caliper/`, 60 transactions, indicative only); this phase redoes it on the real token with the real compliance rules, and with enough distinct senders that the numbers mean something.

What the spike did not settle, and what shapes the task order:

1. **Senders.** The stock Caliper Ethereum connector signs every transaction of a worker with one account, and one account sending many transactions at once is limited by its own nonce. So the load needs N senders. The connector can derive one account per worker from `fromAddressSeed` (path `m/44'/60'/<workerIndex>'/0/0`), so **N wallets means N workers, each owning one wallet**, and the same wallets have to be known to FireFly's signer for the second round.
2. **The token is already deployed.** The Ethereum connector normally deploys its contract in Caliper's install step. Whether a configured `address` lets it use the deployed `COIN` is untested.
3. **FireFly's signer has to know the new keys.** It reads keystore files from `network-config/firefly/signer-data/keystore` at start. Whether it picks up new files without a restart is untested.
4. **Every wallet must be a verified T-REX investor** (identity, registry entry, KYC claim) and hold `COIN`, or `transfer` reverts. That is four writes per wallet through FireFly, so setup can take longer than the rounds (risk R7).

Design choices that apply to every task:
- **Layers (`PROJECT.md`).** Pure logic in `src/core/` (derive wallet addresses from the seed, the setup plan, the config snapshot). I/O in `src/adapters/` and `scripts/stack.py` (write keystores, restart the signer, run the onboarding through FireFly). Caliper and its two connectors are JavaScript under `perf/`, a separate sub-project with its own `package.json` (PRD US-012).
- **Reuse (CLAUDE §12).** Wallet setup reuses the Phase 2 onboarding functions (`register_identities`, `issue_claims`) and `keystore_files`, and the FireFly connector reuses the shape of `spike/caliper/connector/firefly-connector.js`. The Python side is not rewritten in Node.
- **Same load on both layers.** The same N workers, the same wallets, the same recipient pattern (each wallet sends to the next one in a ring, so every recipient is verified), the same offered rate and transaction count. Only the path differs.
- **No numbers without their configuration** (plan anti-gate). Every report is saved next to a small config snapshot (block period and gas limit read from `network-config/genesis.json`, validator and RPC count, N, offered rate, transaction count, image versions), and the results note is built from those files.
- **Side effect on the demo state.** Funding the wallets mints new `COIN`, which breaks two existing integration invariants (`totalSupply == 1000` and `anson + beatrice == 1000`). So the setup integration test burns what it minted in its teardown, and the README says to `reset` after benchmarking (Open Question 3).
- **Tests.** Unit tests need no Docker or Node. The setup has an integration test. The two rounds have no pass or fail (UC-10): their check is that both reports exist, the numbers come from a clean stack, and the note states the configuration. Round runs are verified by hand on the live stack and recorded.
- **Verification commands.** Python ones from `PROJECT.md`: `ruff check .`, `mypy .`, `pytest`, `pytest -m integration`. **There is no Caliper command in `PROJECT.md` yet** (`TBD`): Task 1 defines the `npm` scripts in `perf/package.json`, and Task 7 adds them to `PROJECT.md` (Open Question 5).
- **Working branch:** `main`, committing per task.

Sizes: no task is L or larger. Tasks 1 to 6 are M, Task 7 is S.

---

## Group A — `perf/` runs, and N verified wallets exist (plan steps 1 and 2, DL-5.1)

### Task 1: `perf/` with Caliper 0.6.0 and a trivial round against the deployed `COIN`

**Description:** Create `perf/` with its own `package.json` (Caliper `caliper-cli`, `caliper-core` and `caliper-ethereum` at exactly 0.6.0, `web3@1.3.0` installed by hand with `npm install --no-save web3@1.3.0` because `caliper bind` fails on Windows, per spike Risk 5), the `ws://localhost:8546` network config for `besu-rpc-anson`, and `npm` scripts that run a round. The trivial round is a read-only `COIN.name()` against the **already deployed** token at the address in `deployed-addresses.json`, run with `--caliper-flow-skip-install`. This is the riskiest Caliper unknown, so it goes first; the probes below are recorded in `docs/spike-results.md`.

**Acceptance criteria:**
- [x] `cd perf && npm ci && npm install --no-save web3@1.3.0` then the trivial round runs against the live stack and writes `report.html` (gitignored); the exact versions are pinned in a committed `package-lock.json`
- [x] Probe A recorded: a configured contract `address` with `--caliper-flow-skip-install` lets the connector call the deployed `COIN` (or, if not, what works instead)
- [x] Probe B recorded: how a worker gets its own sender (`fromAddressSeed` and the derivation of worker 0, 1, 2, printed so Task 2 can test against them); the zero-gas write itself is first exercised in Task 3, see the status

**Verification:**
- [x] Tests pass: no unit tests; the round exits 0 and the report exists (`npm run` script defined here)
- [x] Checks clean: `ruff check .` and `mypy .` unchanged; `npm ci` has no new vulnerability beyond the ones the spike already accepted (deprecated Caliper dependencies, spike Risk 5)

**Dependencies:** None (Phase 4 done, stack up and deployed)

**Files likely touched:**
- `perf/package.json`, `perf/package-lock.json`, `perf/network/ethereum.json`, `perf/benchmarks/smoke.yaml`, `perf/workload/name.js`, `perf/README.md` (new)
- `docs/spike-results.md` (Phase 5 probes)

**Size:** M

**Status:** Done 2026-10-04. `npm run smoke` runs 10 of 10 and writes `report.html`. Probe A: the network config must carry `abi` inline beside `address`, otherwise the worker fails (the connector only reads the ABI when it deploys). Probe B: `fromAddressSeed` gives each worker `m/44'/60'/<i>'/0/0`; vectors for the seed `besu-with-firefly perf demo seed` are in `docs/spike-results.md`. A write from a derived key was not run here (it needs a verified wallet, Task 3). `perf/package-lock.json` pins Caliper 0.6.0; `web3@1.3.0` stays a manual `--no-save` install. Commands: `npm run smoke`, `npm run prepare-run`, `node lib/derive.js` (Open Question 5; `PROJECT.md` gets them in Task 7).

### Task 2: N wallets from a seed, known to FireFly's signer

**Description:** Pure code in `src/core/` derives the wallets from a demo seed with the same scheme as Caliper (BIP32 master key from the seed's UTF-8 bytes, path `m/44'/60'/<i>'/0/0`, built on `eth_keys`, already installed with `eth-account`, so no new dependency), returning `Wallet` objects named `perf-001` and so on. An adapter writes their keystores with the existing `keystore_files` into the signer's keystore folder and makes the signer load them. First step: probe whether the signer needs a restart (Open Question 2); the answer decides between a file write plus `docker restart firefly-signer` and something lighter. Keystore files for perf wallets are gitignored (they are generated per N), and `init` and the committed Phase 1 and 2 keystores stay untouched.

**Acceptance criteria:**
- [x] The derived addresses for workers 0, 1 and 2 equal the ones Caliper's own derivation printed in Task 1 (a recorded test vector, unit-tested), N is configurable, and the same seed always gives the same wallets
- [x] After the adapter runs for N wallets, FireFly's signer lists all N addresses (`eth_accounts` against the signer, through `docker exec` since its port is not published), and the existing wallets are still listed
- [x] Running it twice changes nothing the second time; running it for a smaller N does not remove wallets already loaded

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration tests/integration/test_perf_wallets.py`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 1 (the test vector)

**Files likely touched:**
- `src/core/perf/wallets.py` (new), `src/adapters/perf_wallets.py` (new), `.gitignore`
- `tests/unit/core/test_perf_wallets.py`, `tests/unit/adapters/test_perf_wallets.py`, `tests/integration/test_perf_wallets.py` (new)

**Size:** M

**Status:** Done 2026-10-04. Test-first (8 core, 8 adapter unit tests, 2 integration tests). Probe in `docs/spike-results.md`: the signer needs a restart (Open Question 2 default taken) and takes the address from the file name, so keystores are named by address and `.gitignore` ignores new files in the keystore folder (tracked ones stay tracked; a new committed wallet needs `git add -f`). `eth-keys` is now a declared dependency (it was only transitive). Files are written only when missing, so a smaller N later removes nothing.

### Task 3: `perf-setup`: the wallets become verified investors holding `COIN`

**Description:** `python scripts/stack.py perf-setup --wallets N --coins K` runs Task 2, then for each perf wallet registers an identity, adds the KYC claim and mints `K` COIN to it, all through FireFly and the existing onboarding functions, skipping what is already true (a second run sends nothing). Setup duration is measured and printed (R7). A pure function decides what is still missing per wallet, like `registration_steps` does today.

**Acceptance criteria:**
- [x] `perf-setup --wallets 3 --coins 100` on a deployed stack leaves 3 wallets with `isVerified == true` and `balanceOf == 100 COIN` (checked through the contract API), and prints its duration
- [x] A second identical run sends no transaction; `--wallets 4` afterwards onboards only the fourth
- [x] The integration test mints, checks, then burns what it minted in teardown, so `totalSupply` is 1000 again and the existing supply tests still pass

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration tests/integration/test_perf_setup.py`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 2

**Files likely touched:**
- `src/core/perf/setup.py` (new), `src/adapters/perf_setup.py` (new), `src/adapters/stack_cli.py`, `src/adapters/trex_onboard.py` (only if the existing functions need the account list passed in)
- `tests/unit/core/test_perf_setup.py`, `tests/unit/adapters/test_perf_setup.py`, `tests/unit/adapters/test_stack_cli.py`, `tests/integration/test_perf_setup.py`

**Size:** M

**Status:** Done 2026-10-04. Test-first (7 core and adapter unit tests plus 2 CLI tests, 1 integration test). `register_identities` and `issue_claims` got a `names` parameter (default unchanged), so the Phase 2 code is reused as is. Mint tops each wallet up to the target and its idempotency key holds the starting balance, so a later top-up never reuses an earlier key. Measured on the live stack: 3 wallets in 38 s (about 13 s per wallet, so N=10 is about 2 minutes), a second run in 1.4 s sending nothing, and a fourth wallet added in 10 s. The test burns the minted COIN in its teardown and `totalSupply` is 1000 again. Found and fixed on the way (own commit): the `reset` unit tests ran `main(["reset"])` with the default paths, so every `pytest` run deleted the real `deployed-addresses.json` and the contents of `paladin-runtime/` of a running stack; they now use `tmp_path`.

---

## Checkpoint: After Tasks 1–3

- [x] `ruff check .`, `mypy .`, `pytest` (558) pass, and `pytest -m integration` ran 116 tests with 115 passing; the one failure, `test_the_signer_holds_the_three_demo_wallets`, compared the signer's accounts for equality with the three demo wallets and so failed once perf keystores were loaded. It now checks that the demo wallets are among the signer's accounts, and passes alone; the full suite is rerun in Task 6 and Task 7. Supply is back to 1000 after the new tests
- [x] The trivial Caliper round runs and the probes are recorded (two in Task 1, one in Task 2)
- [x] N wallets verified on-chain, N configurable, setup duration printed (about 13 s per wallet)
- [ ] Human review before proceeding (**waiting for Howin**)

---

## Group B — The two rounds (plan steps 3 and 4, DL-5.2)

### Task 4: Chain-layer round: `COIN.transfer` direct over JSON-RPC

**Description:** A Caliper workload (`perf/workload/transfer.js`) where worker `i` sends `COIN.transfer(wallet[(i+1) mod N], amount)` from its own derived wallet, through the stock Ethereum connector against `besu-rpc-anson`, with `transactionConfirmationBlocks: 1` as in the spike. The benchmark file takes N workers, the offered rate and the transaction count from one place (the same values Task 5 uses). `npm run round:chain` writes the report and a config snapshot (block period and gas limit read from `network-config/genesis.json`, N, rate, count, Besu image).

**Acceptance criteria:**
- [x] The round runs with N=10 on a deployed and set-up stack, every transaction succeeds, and the report shows throughput and average, minimum and maximum latency
- [x] The snapshot file is written with the round and holds the genesis block period (2) and gas limit, N, the offered rate, the transaction count and the validator and RPC node count
- [x] After the round, the sum of the N balances is unchanged (transfers only move `COIN`), checked by a small script

**Verification:**
- [x] Tests pass: `npm run round:chain` exits 0 (name per Task 1); unit tests for any Python helper
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 3

**Files likely touched:**
- `perf/workload/transfer.js`, `perf/benchmarks/chain.yaml`, `perf/network/ethereum.json`, `perf/package.json`, `perf/README.md`
- `perf/lib/snapshot.js` (new, writes the config snapshot), a balance-sum check script

**Size:** M

**Status:** Done 2026-10-04. `npm run round:chain` (`perf/run.js`) prepares `generated/`, checks that every wallet is verified and funded, runs Caliper, parses its summary table (`lib/report.js`, refuses anything that is not exactly one round), checks the balance sum is unchanged, and writes `results/chain.json` with the snapshot (`lib/snapshot.js`: layer, load, genesis block period and gas limit, validators and RPC nodes, versions). 9 `node --test` tests. First run with N=10, 20 TPS, 600 transfers: 600 of 600 succeeded, 19 TPS, average latency 1.86 s (one run, not a result). Finding: Caliper takes `txNumber` and `tps` as totals split across workers, so the generated benchmark file carries totals. The load comes from one place (`lib/params.js`, env `PERF_*`), and a Python test checks that the seed matches `src/core/perf/wallets.py`. The funded wallets leave COIN supply at 2000 until the next `reset`.

### Task 5: FireFly-layer round: the same transfer through FireFly's contract API

**Description:** A custom Caliper connector (`perf/connector/firefly-connector.js`, from the spike's shape) that sends the same transfer as `POST /apis/coin/invoke/transfer?confirm=true` with `key` set to the worker's wallet address, and marks a transaction successful only for a `Succeeded` operation (the Phase 4 rule: nothing else counts). It reuses `workload/transfer.js` unchanged, so only the path differs, and writes the same snapshot. `npm run round:firefly` runs it.

**Acceptance criteria:**
- [ ] The round runs with the same N, rate and count as Task 4, and the report shows throughput and latency
- [ ] A failed or pending operation is counted as failed, never as success (shown with a unit test of the connector's status mapping, no stack needed)
- [ ] The two snapshots are identical except for the layer, so the two reports are comparable

**Verification:**
- [ ] Tests pass: `npm run round:firefly` exits 0; the connector's status mapping test (a small `node --test` file, no new dependency)
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 4

**Files likely touched:**
- `perf/connector/firefly-connector.js`, `perf/benchmarks/firefly.yaml`, `perf/network/firefly.json`, `perf/test/firefly-connector.test.js`, `perf/package.json`, `perf/README.md`

**Size:** M

---

## Checkpoint: After Tasks 4–5

- [ ] `ruff check .`, `mypy .`, `pytest` pass
- [ ] Both rounds run on the same stack with the same load and write a report and a snapshot each
- [ ] The FireFly round counts only `Succeeded` operations as success
- [ ] Human review before proceeding (**waiting for Howin**)

---

## Group C — Results, reproducibility and documentation (plan step 5 and the exit gate, DL-5.1 to DL-5.3)

### Task 6: Fresh-stack runs and the results note

**Description:** From `python scripts/stack.py reset && up && deploy`, run `perf-setup`, both rounds, and record the numbers; do this twice to show both rounds are reproducible (same order of magnitude, nothing failing). Then write `docs/perf-results.md`: both result sets, the difference between them, the configuration they were measured under (block period 2 s, the gas limit, one validator and one RPC node from D-17, N, rate, count, versions, setup duration), what the numbers do and do not say, and the caveat that they describe this demo configuration, not Besu's limits (R13). Numbers and configuration are copied from the snapshot files, not retyped.

**Acceptance criteria:**
- [ ] Two fresh-stack runs of setup plus both rounds finish with every transaction succeeding, and the note shows both runs
- [ ] The note lists chain-layer and FireFly-layer throughput and latency, the difference, the genesis block period and gas limit, and the caveat; no number appears without its configuration
- [ ] A reader can repeat the runs from the note's commands alone (checked by following it from the top once)

**Verification:**
- [ ] Tests pass: `npm run round:chain` and `npm run round:firefly` exit 0 twice from a fresh stack; `pytest -m integration` still passes before benchmarking
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 4 and 5

**Files likely touched:**
- `docs/perf-results.md` (new)

**Size:** M

### Task 7: Phase 5 documentation and exit gate

**Description:** Update `README.md` (running the benchmark, the supply side effect and the `reset` afterwards), `PROJECT.md` (the `perf-setup` and Caliper commands in the table, the `perf/` layout, the node and npm versions), `docs/deliverables.md` (DL-5.1 to DL-5.3 `Done`, with commands that were actually run), `docs/plan.md` (Phase 5 status with the date and exact result, exit gate boxes) and `docs/spike-results.md` (the probes). Verify the README steps from a fresh clone as in Phases 3 and 4.

**Acceptance criteria:**
- [ ] DL-5.1 to DL-5.3 are `Done` with commands that were run, and `docs/plan.md` marks Phase 5 with the date and result
- [ ] `PROJECT.md` lists every command used in this phase, and `perf/README.md` and the README agree with it
- [ ] `ruff check .`, `mypy .`, `pytest` and `pytest -m integration` pass after a `reset`, `up` and `deploy`

**Verification:**
- [ ] Tests pass: `pytest` and `pytest -m integration` once more on a fresh stack, after the benchmarks have been `reset` away
- [ ] Checks clean: `ruff check .` and `mypy .`; README steps checked from a fresh clone

**Dependencies:** Task 6

**Files likely touched:**
- `README.md`, `PROJECT.md`, `docs/deliverables.md`, `docs/plan.md`, `docs/spike-results.md`

**Size:** S

---

## Checkpoint: After Task 7 (Phase 5 exit gate)

- [ ] All DL-5.x deliverables verified
- [ ] Both rounds reproducible from a fresh `python scripts/stack.py reset && python scripts/stack.py up && python scripts/stack.py deploy` (plus `perf-setup`)
- [ ] Results note committed, with the configuration beside every number
- [ ] Human review of the Phase 5 exit gate (**waiting for Howin**)

---

## Open Questions

| # | Question | Owner | Recommended default |
|---|---|---|---|
| 1 | Where does wallet setup live? The Phase 2 onboarding logic is Python, `perf/` is Node. | Howin | Python: `python scripts/stack.py perf-setup`, reusing the onboarding functions; Node only runs Caliper |
| 2 | FireFly's signer reads keystores at start. If Task 2's probe shows it does not pick up new files, restart the signer (a few seconds, FireFly reconnects) or preload a fixed set of perf wallets at `init` (committed, demo, no restart, but N has a ceiling and Phase 1 and 2 files change)? | Howin | Restart `firefly-signer` from the setup adapter; keep `init` and the committed keystores untouched |
| 3 | Funding the wallets mints new `COIN`, which breaks `totalSupply == 1000` and `anson + beatrice == 1000` in the existing tests until a `reset`. | Howin | The setup integration test burns what it minted; the README says to `reset` after a benchmark. Do not change the existing tests |
| 4 | Load parameters. The spike used one key at 20 TPS for 60 transactions. | Howin | N=10 workers, offered rate 20 TPS in total (2 per worker), 600 transactions, the same on both layers; N, rate and count are options, so a second, higher rate can be added later |
| 5 | There is no Caliper command in `PROJECT.md` (`TBD`). | Claude, in Task 1 | Define `npm run round:chain`, `round:firefly` and the smoke round in `perf/package.json` in Task 1, and add them to `PROJECT.md` in Task 7 |
| 6 | Phase 4's and Phase 3's "human review" boxes (`tasks/phase-4-cli.md`, `tasks/phase-3-paladin.md`) are still open. | Howin | Tick them when convenient; nothing in Phase 5 depends on them |

## Notes

- Out of scope (plan §4 Phase 5): Paladin benchmarks, tuning Besu for throughput, more validators, a benchmark of the CLI. Numbers describe one validator with a 2 s block period (D-17); they are not Besu's limits.
- Caliper 0.6.0 pulls deprecated dependencies (`web3@1.3.0`, old `glob`, `core-js` 2; spike Risk 5). Accepted for a local demo; versions are pinned in the lock file.
- Round runs are measured on a laptop already running 10 containers, so run-to-run spread is expected; the note reports both runs instead of one number.
- Phase 5 is about 3 to 5 days (plan).
