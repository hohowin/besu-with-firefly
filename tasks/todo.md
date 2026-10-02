# Tasks — Phase 2: FireFly + ERC-3643

> Source: `docs/plan.md` Phase 2 (steps 1 to 7), `docs/prd.md` US-004 to US-008, FR-3 to FR-7 and FR-11, `docs/deliverables.md` DL-2.1 to DL-2.6, `docs/use-cases.md` UC-04 to UC-07, `docs/spike-results.md` (Risks 1, 3, 4, 7 and "Versions to pin"). Decisions: D-02 (FireFly gateway mode), D-03 (hand-written Compose), D-04 (official T-REX, deployed through FireFly), D-07 (register, claim, mint, transfer), D-08 (Shanghai, `zeroBaseFee`), D-10 (demo keys committed), D-16 (`python scripts/stack.py`). Phase 1 is complete and reviewed; its task list is `tasks/phase-1-network.md`.
> **Status: approved by Howin on 2026-10-02 (all Open Questions answered as recommended).**

## Overview

Phase 2 attaches FireFly (gateway mode) to the Besu network from Phase 1, deploys the official ERC-3643 (T-REX) suite through FireFly's deploy API as `COIN`, registers a contract interface and API for it, then proves onboarding, a compliant transfer and an on-chain rejection. Work is sliced so the riskiest unknown, the dependency order and constructor arguments of the full T-REX suite (never done end to end; plan risk R3), is hit as early as FireFly can carry it, and every later task builds on a working `deploy`.

Design choices that apply to every task:
- **Layers (`PROJECT.md`).** Pure logic in `src/core/` (the deploy plan and its ordering, skip-if-already-true decisions, claim hashing and signing, config and keystore builders). I/O in `src/adapters/` (FireFly HTTP client, file writing, Docker) and `scripts/stack.py`.
- **FireFly is the only writer for `COIN` traffic.** Contracts are deployed and called through FireFly, never through a direct RPC signer (D-04, architecture §7 B). Direct JSON-RPC is used only to read and check (`eth_getCode`).
- **Hand-written Compose, four FireFly containers** (Postgres, signer, evmconnect, core), pinned by digest as in the spike. No data exchange, no IPFS, no `ff start`. FireFly's signer points at `besu-rpc-anson` on the shared Compose network, not `host.docker.internal`.
- **Config and keystores are generated, then committed** (D-10). The three demo wallets already exist in `network-config/wallets.json`; `init` derives the signer keystores and the FireFly config (`defaultKey` = admin) from them, so `init --force` stays consistent.
- **Contract artifacts come from the pinned `@tokenysolutions/t-rex` and OnchainID npm packages** (Solidity 0.8.17, no PUSH0, sizes already checked in the spike). They are installed with `npm ci`, not copied into the repo. See Open Questions 1 and 2.
- **Write calls pass a stable `idempotencyKey`.** HTTP 409 with `FF10431` means "already submitted", not an error (spike Risk 7). Onboarding also checks state first (skip-if-already-true).
- **Facts to confirm early (spike gaps).** The status value of a *reverted* operation was never observed (it is observed in Task 12). The exact T-REX deploy order and constructor arguments are found in Task 5, before any code depends on them.
- **Tests.** Unit tests need no Docker. Integration tests use the real stack. A session fixture runs `deploy` once, so the 5-minute suite does not deploy per test.
- **Verification commands** (from `PROJECT.md`): `ruff check .`, `mypy .`, `pytest`, `pytest -m integration`, `docker compose config -q`.
- **Working branch:** `main`, committing per task (as in Phase 1).

Sizes: no task is L or larger. Tasks 7 and 9 are the largest (M).

---

## Group A — FireFly runs (plan step 1, DL-2.1)

### Task 1: `init` generates the FireFly signer keystores and core config

**Description:** Extend `stack.py init` so that, from `network-config/wallets.json`, it writes the FireFly signer keystore for `admin`, `anson` and `beatrice` (per key an Ethereum keystore JSON named by address, a `.toml` pointing at it, and a shared `password` file, spike Risk 1), plus `firefly/` config files for core, evmconnect and signer. Core's `namespaces` block is the working gateway-mode block from the spike with `defaultKey` = the admin address, `multiparty.enabled: false`. evmconnect gets `fixedGasPrice: 0`, `gasOracle.mode: fixed`, `confirmations.required: 0`. The signer's backend is `http://besu-rpc-anson:8545`, chainId `20260916`. Builders are pure (`src/core/firefly/`), writing is in the existing init adapter. Same refuse-without-`--force` rule as Phase 1.

**Acceptance criteria:**
- [x] For each wallet, the keystore decrypts with the shared password to the private key in `wallets.json`, and the file is named by the wallet's address (tested by re-deriving the address)
- [x] The generated core config has `defaultKey` equal to the admin address, and the signer config's backend is `besu-rpc-anson`, not `host.docker.internal` (tested on the pure builders)
- [x] `init` without `--force` still refuses and changes nothing; with `--force` it regenerates everything consistently

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k init`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** None (Phase 1 done)

**Files likely touched:**
- `src/core/firefly/config.py`, `src/core/firefly/keystore.py`
- `src/adapters/besu_config.py` (or a sibling adapter for the FireFly files)
- `firefly/` (generated, committed, demo only), `network-config/README.md`
- `tests/unit/core/test_firefly_config.py`, `tests/unit/core/test_keystore.py`

**Size:** M

**Status:** Done 2026-10-02. Test-first. Files are generated under `network-config/firefly/` (not a top-level `firefly/`), so `init` stays the single owner of everything it generates and its tests use a temporary folder. The signer keystores use scrypt with `n=4096` (public demo keys; full cost makes the signer start slowly). `init --force` was re-run, so every committed key, the genesis and the wallets are new; the real keystores decrypt to the keys in `wallets.json` and `defaultKey` is the admin address. 108 unit tests, `ruff` and `mypy` clean, `init` integration test passes, and the Phase 1 network tests (21) pass on the new keys.

### Task 2: FireFly containers start and report ready

**Description:** Add `firefly-postgres`, `firefly-signer`, `firefly-evmconnect` and `firefly-core` to `docker-compose.yml`, images pinned by the digests in `docs/spike-results.md`, mounting the Task 1 files, on the existing `besu` network with fixed IPs outside the Besu range. Publish only FireFly's HTTP port `5000` (admin/SPI `5101` stays internal, Open Question 7). Service order: Postgres, signer, evmconnect, core. The signer must reach `besu-rpc-anson`; no Besu node of FireFly's own.

**Acceptance criteria:**
- [x] `docker compose config -q` exits 0, and the four FireFly services reach `running` with no restart loop
- [x] `GET http://localhost:5000/api/v1/status` reports the `default` namespace ready with the `ethereum` blockchain plugin and `multiparty.enabled: false`
- [x] The signer holds the three keys (`admin`, `anson`, `beatrice`), asked through its own `eth_accounts`; the default key is the admin address in the generated config (FireFly's status document does not show it; Task 6's deploys sign with it)

**Verification:**
- [x] Tests pass: `pytest -m integration -k firefly_status` (new test, red before the Compose change)
- [x] Checks clean: `docker compose config -q`, `ruff check .`, `mypy .`

**Dependencies:** Task 1

**Files likely touched:**
- `docker-compose.yml`
- `tests/integration/test_firefly_status.py`
- `tests/support/firefly.py` (a tiny stdlib HTTP helper for tests; the real adapter is Task 4)

**Size:** M

**Status:** Done 2026-10-02. Test-first (4 integration tests, red before the Compose change): the four containers are healthy, `/api/v1/status` shows the `default` namespace with the `ethereum` plugin and `multiparty` false, the signer's `eth_accounts` equals the three wallets, and the signer's chain id and height follow `besu-rpc-anson`. All four FireFly images have `curl`, so each has a real Compose healthcheck and `up` needs no change for them. FireFly containers use service names, not fixed IPs. **Found and fixed:** Besu's own image healthcheck (`[ -f /tmp/pid ]`, 1 s timeout, 5 s start period) made containers `unhealthy` during a busy cold start, which aborted `docker compose up` through `depends_on` and explains the failed `up` seen from the clean clone in Phase 1. `x-besu` now overrides it with the same check and patient limits (10 s timeout, 60 s start period, 30 retries). Three consecutive `reset` then `up`: exit 0 each time, about 106 s, first block immediately after. The 120 s default of `up --timeout` is now too tight (Task 3 raises it).

### Task 3: `stack.py up` brings FireFly up with no manual step

**Description:** The FireFly images may have no Docker healthcheck, and `DockerStack.up` today treats "no health" as not healthy. Make `up` wait for each service by what it offers: Besu services as now, FireFly core by `GET /api/v1/status` ready, the others by `running` (or a healthcheck added in Compose where the image has the tooling). `up` stays idempotent and exits non-zero with the name of the service that is not ready. Update the Phase 1 integration `stack` fixture only if needed.

**Added 2026-10-02 (found during Tasks 1 and 2):** raise the default `up --timeout` from 120 s to 300 s (a cold `up` with FireFly takes about 106 s). Also: on a cold start the QBFT chain can take minutes to produce its first block (round timeouts back off while the validators are still connecting; seen again on an idle machine, block #9 only 5 minutes after `up`). `deploy` needs a producing chain, so `up` must also wait until `eth_blockNumber` on both RPC nodes is at least 1, with a generous limit. Measure the stall over several `reset`/`up` runs and record it in the task status.

**Acceptance criteria:**
- [x] `python scripts/stack.py reset` then `python scripts/stack.py up` ends with all 10 services ready, FireFly status ready and both RPC nodes past block 0, with no other command
- [x] A service that never becomes ready makes `up` exit 1 and name that service (unit-tested with a fake runner)
- [x] Running `up` twice is harmless

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k "validators or rpc or firefly"`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 2

**Files likely touched:**
- `src/core/network/health.py`, `src/adapters/docker_stack.py`, `src/adapters/stack_cli.py`, a small JSON-RPC reader in `src/adapters/`
- `tests/unit/core/test_health.py`, `tests/unit/adapters/test_docker_stack.py`

**Size:** S

**Status:** Done 2026-10-02. Test-first. The FireFly services already have Compose healthchecks (Task 2), so `DockerStack.up` needed no health change. What `up` gained: after every container is healthy it waits until both RPC nodes report a block above 0 (pure `nodes_without_blocks`, a JSON-RPC reader adapter in `src/adapters/rpc.py` tested against a local HTTP server) and names the node that is unreachable or still at block 0; the default timeout is 300 s and the integration `stack` fixture uses the same reader. FireFly readiness comes from its healthcheck, which is `GET /api/v1/status`. `test_reset` now checks that blocks exist and FireFly is ready right after `up` returns, and its genesis check compares the height with the elapsed time (the old fixed limit of 10 blocks no longer holds because `up` takes about 100 s). 115 unit tests, `ruff` and `mypy` clean.

### Task 4: FireFly HTTP client adapter

**Description:** A small adapter in `src/adapters/firefly.py` (standard library `urllib`, Open Question 3) for the calls Phase 2 needs: status, contract deploy, contract invoke, contract query, interface and API registration, and reading an operation's final status with bounded polling. Deploy and invoke accept an `idempotencyKey`; a 409 `FF10431` is returned as "already submitted" with the original transaction id (spike Risk 7). Errors carry FireFly's message. The pure parts (status classification, request bodies, `FF10431` parsing) are in `src/core/firefly/`; the HTTP transport is injected so the unit tests need no Docker.

**Acceptance criteria:**
- [x] A fake transport proves: bodies are built correctly, a 409 `FF10431` is classified as already-submitted (not an error), a `Succeeded` operation returns, a `Failed` operation raises with FireFly's error text, and a never-final operation times out with the operation id
- [x] Against the live stack, `status()` returns the ready status document, an unknown operation id and a query to a non-existent contract both give a `FireflyError` carrying FireFly's own message, and an unreachable FireFly gives a `FireflyError` that names the request (no deploy needed)
- [x] The module has no hidden global state and no `print`

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k firefly_client`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 3

**Files likely touched:**
- `src/core/firefly/operations.py`, `src/adapters/firefly.py`
- `tests/unit/core/test_operations.py`, `tests/unit/adapters/test_firefly.py`
- `tests/integration/test_firefly_client.py`

**Size:** M

**Status:** Done 2026-10-02. Test-first (24 new unit tests with a fake transport, 4 integration tests). Pure request bodies and response reading are in `src/core/firefly/operations.py`; the client, its exceptions (`FireflyError`, `OperationFailed`, `OperationTimeout`, `AlreadySubmitted`) and the `urllib` transport are in `src/adapters/firefly.py`. Writes use `?confirm=true` and a still-pending operation is polled with a bound. Real FireFly message seen: an unknown operation id is `HTTP 404: FF00164: No result found`. Interface and API registration are added in Task 8, as planned.

## Checkpoint: After Tasks 1–4

- [x] `ruff check .`, `mypy .` and `pytest` clean (138 unit tests)
- [x] `python scripts/stack.py reset && python scripts/stack.py up` leaves 10 ready services and FireFly status ready, through `besu-rpc-anson`
- [x] Phase 1 integration tests still pass: the whole `pytest -m integration` suite, 34 passed in 6 min on a freshly reset and started stack
- [x] M2.1 exit gate from `docs/plan.md` step 1 holds
- [x] Human review before proceeding (Howin, 2026-10-02: ok)

---

## Group B — T-REX deployed as `COIN` (plan steps 2 to 4, DL-2.2, DL-2.3)

### Task 5: T-REX artifacts, deploy order and sizes (the fail-fast task)

**Description:** Pin `@tokenysolutions/t-rex` (4.1.6) and the OnchainID package it depends on in `contracts/package.json` (`npm ci`). Write the pure **deploy plan** in `src/core/trex/`: the ordered list of contracts to deploy (implementations, implementation authorities, OnchainID factory pieces, `TREXFactory`) with how each constructor argument is obtained from earlier addresses, plus the ABI and bytecode loader (an adapter). Find the order and arguments by reading the package's own deployment scripts and tests, and record the result in `docs/spike-results.md` under a new "Phase 2 findings" section. Check every deployed size against 24 576 bytes and every init size against 49 152.

**Acceptance criteria:**
- [x] The plan lists every contract with its constructor arguments and the earlier contract each argument comes from; a unit test proves every reference points to something deployed earlier and no cycle exists
- [x] A test fails if any deployed size is over 24 576 bytes or any init size is over 49 152 (sizes read from the installed artifacts)
- [x] `docs/spike-results.md` records the order, the arguments and any size margin, and states clearly if the full suite cannot be deployed as planned (then stop and raise D-04; plan risk R3 fallback)

**Verification:**
- [x] Tests pass: `pytest tests/unit` (reads the installed artifacts, so the test runs after `npm ci`; it skips with a clear message if `contracts/node_modules` is missing)
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** None (can start after Task 1; does not need FireFly)

**Files likely touched:**
- `contracts/package.json`, `contracts/package-lock.json`
- `src/core/trex/plan.py`, `src/adapters/trex_artifacts.py`
- `tests/unit/core/test_trex_plan.py`, `tests/unit/adapters/test_trex_artifacts.py`
- `docs/spike-results.md`, `.gitignore` (`contracts/node_modules/`)

**Size:** M

**Status:** Done 2026-10-02. Test-first (42 unit tests, red before the code). **Finding:** `@tokenysolutions/t-rex` does not ship `IdFactory`, so `@onchain-id/solidity` 2.1.0 is pinned as well (its ABIs match what t-rex bundles; 2.2.x changes `Identity`). The plan has 12 deploys and 3 wiring calls (`addAndUseTREXVersion`, `setTREXFactory`, `addTokenFactory`); a test checks every constructor's argument count, every called method and its input count, and the size limits against the real artifacts. Largest is `TREXFactory`, 23,495 bytes, 1,081 under the limit. D-04 and R3 hold; order, arguments and the size table are in `docs/spike-results.md` "Phase 2 findings". The unit test module skips with a hint if `npm ci` was not run in `contracts/`.

### Task 6: Deploy the T-REX infrastructure contracts through FireFly

**Description:** Add `python scripts/stack.py deploy`, which loads the Task 5 plan and deploys the infrastructure contracts in order through the Task 4 client (`POST /contracts/deploy`, key `admin`), checking each address against `eth_getCode` as it goes. Stop at the first failure and name the contract and FireFly's error. It writes `deployed-addresses.json` (gitignored, Open Question 6) after each success. Everything up to, but not including, creating the `COIN` token.

**Acceptance criteria:**
- [x] Every deployed address is non-zero and has code on-chain (`eth_getCode`), and FireFly shows a deploy operation per contract
- [x] A deploy failure stops the run, names the contract, prints FireFly's error, and exits non-zero (unit-tested with a fake client)
- [x] The contracts are deployed through FireFly, not a direct RPC signer (the integration test lists FireFly's operations and sees one per contract)

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k deploy_infrastructure`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 4, 5

**Files likely touched:**
- `src/adapters/stack_cli.py`, `src/adapters/trex_deploy.py`
- `tests/unit/adapters/test_trex_deploy.py`, `tests/integration/test_deploy.py`
- `.gitignore`

**Size:** M

**Status:** Done 2026-10-02. Test-first (31 new unit tests, 5 integration tests). From a reset stack, `python scripts/stack.py deploy` deploys the 12 contracts and makes the 3 wiring calls in about 33 s; every address has the pinned artifact's code (checked by size) and a `Succeeded` FireFly deploy operation. **Found on the real chain:** (1) the plan order from Task 5 was wrong: `TREXFactory`'s constructor reverts unless `addAndUseTREXVersion` already ran, so that call now comes before the factory (plan test added, `docs/spike-results.md` corrected); (2) a failed transaction keeps its idempotency key, so a retry got a 409. The runner now checks the earlier transaction and retries under a new key when it failed, treats a succeeded call as done, and asks for `reset` for a deploy whose address was not recorded. The same run also showed that a reverted deploy comes back as HTTP 500 with the revert text and that the final status is `Failed` (recorded for Task 12). `deployed-addresses.json` is gitignored. A second `deploy` sends nothing new.

### Task 7: Create the `COIN` token through the factory

**Description:** Use the deployed `TREXFactory` to create the token suite for `COIN`: call `deployTREXSuite` through FireFly's invoke API as `admin` with token details (name `Coin`, symbol `COIN`, 18 decimals), claim topics (KYC), trusted issuers, and the compliance setup, then read the created token, IdentityRegistry, IdentityRegistryStorage, ClaimTopicsRegistry, TrustedIssuersRegistry and ModularCompliance addresses from the factory (`getToken(salt)` and the proxies' own getters) and add them to `deployed-addresses.json`. Add the deployment of the `ClaimIssuer` contract that Admin will use to sign KYC claims (needed in Task 10). If the factory call cannot fit the plan, raise it as a change to D-04.

**Acceptance criteria:**
- [x] `deployed-addresses.json` contains the token and every registry address, all non-zero, each with code on-chain
- [x] `name()` and `symbol()` on the token read back `Coin` and `COIN` (read through FireFly's query API with FireFly-generated methods, since the interface is registered in Task 8)
- [x] The token's IdentityRegistry, ClaimTopicsRegistry and TrustedIssuersRegistry are the contracts in `deployed-addresses.json` (read from the token, not assumed)

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k "deploy and coin"`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 6

**Files likely touched:**
- `src/core/trex/plan.py` (token suite arguments), `src/adapters/trex_deploy.py`
- `tests/integration/test_deploy.py`, `tests/unit/core/test_trex_plan.py`

**Size:** M

**Status:** Done 2026-10-02. Test-first. `deployTREXSuite` is now the last step of the plan (so idempotency, retry and the unit tests of Task 6 apply to it); `read_suite` (new `src/adapters/trex_suite.py`) reads the token and its five proxies back from the factory and the token and checks `Coin`/`COIN` and code on chain. From a reset stack, `deploy` creates COIN on the first try (one transaction, about 6 s). **Caught by a real-ABI test:** the registry getter is `identityStorage`; my fake client had accepted the wrong name, so a test now runs `read_suite` against the real artifacts' method names. 7 deploy integration tests (from a reset stack, `deploy` took about 2 minutes this time, 33 s for the infrastructure alone earlier; the cold start of the whole stack varies). `deployed-addresses.json` now has 18 names, the 12 plan contracts plus the six suite contracts.

### Task 8: Register the contract interface and API for `COIN` and the IdentityRegistry

**Description:** Generate a FireFly contract interface from each needed ABI (Token, IdentityRegistry; plus what Tasks 10 to 12 call), register it, and create a contract API per deployed address (`coin`, `identity-registry`) through the Task 4 client. Registration is part of `deploy` and is idempotent (an already-registered interface or API is reused, not an error). The plan's gate asks for a write through the API; `mint` needs a verified recipient, so the write checked here is `unpause()` on the token (Open Question 5), which also has to happen before any transfer. `mint` through the API is proved in Task 11.

**Acceptance criteria:**
- [x] A read (`balanceOf`, `name`) and a write (`unpause`, then `paused` reads `false`) both succeed through the generated API as `admin`
- [x] The APIs appear in FireFly (`GET /apis`) and the interfaces carry the ABIs
- [x] Running `deploy` again does not create duplicates and does not fail

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k "deploy and api"`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 7

**Files likely touched:**
- `src/core/firefly/interfaces.py` (pure ABI to interface request builder), `src/adapters/firefly.py`, `src/adapters/trex_deploy.py`
- `tests/unit/core/test_interfaces.py`, `tests/integration/test_deploy.py`

**Size:** M

**Status:** Done 2026-10-02. Test-first (22 new unit tests, 5 integration tests). `deploy` now also registers the interfaces and contract APIs `coin` (Token ABI) and `identity-registry` (IdentityRegistry ABI) and unpauses the token as Admin through the `coin` API when it is still paused (a new T-REX token is paused). Reads (`name`, `symbol`, `balanceOf`, `paused`) and the write (`unpause`) work through the generated API; a second `deploy` creates no duplicate interface or API and reports `already unpaused`. Real behaviour recorded in `docs/spike-results.md`: a repeated registration is HTTP 409 `FF10407`, so the client lists first; an interface's methods need `?fetchchildren=true`. The shared `deployed` fixture (runs `deploy`, which only does what is missing) moved to `tests/integration/conftest.py`.

## Checkpoint: After Tasks 5–8

- [x] `ruff check .`, `mypy .` and `pytest` clean (227 unit tests)
- [x] `python scripts/stack.py up && python scripts/stack.py deploy` gives a working `COIN`: addresses non-zero with code, `Coin`/`COIN`, read and write through the API (full `pytest -m integration` on a freshly reset stack: 46 passed in 8.5 min)
- [x] The Task 5 findings are in `docs/spike-results.md`, and no plan assumption (D-04, R3) was broken (one correction: the order of `addAndUseTREXVersion`, found on the chain)
- [x] Human review before proceeding (Howin, 2026-10-02: ok)

---

## Group C — Onboarding, transfer, rejection (plan steps 5 and 6, DL-2.4, DL-2.5)

### Task 9: Register identities (OnchainID and IdentityRegistry), skip if already true

**Description:** Pure onboarding logic in `src/core/trex/onboarding.py`: given the observed state (`isRegistered`), return the list of steps still needed, so a second run sends nothing. Adapter: for Anson and Beatrice, create an OnchainID through the OnchainID factory (`createIdentity(wallet, salt)`), then `registerIdentity(wallet, identity, country)` on the IdentityRegistry as Admin (the token's registered agent), all through FireFly. A step runs only if the state says it is missing. Add `python scripts/stack.py onboard` (or an `onboard` step of `deploy`, decided with Open Question 8) so it can be re-run.

**Acceptance criteria:**
- [x] After the step, `isRegistered` is true for Anson and Beatrice and false for Admin
- [x] A second run sends **no** FireFly write (the integration test counts FireFly operations before and after)
- [x] The pure logic is unit-tested for each state (nothing done, partly done, all done)

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k onboarding_register`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 8

**Files likely touched:**
- `src/core/trex/onboarding.py`, `src/adapters/trex_onboard.py`, `src/adapters/stack_cli.py`
- `tests/unit/core/test_onboarding.py`, `tests/integration/test_onboarding.py`

**Size:** M

**Status:** Done 2026-10-02. Test-first (11 unit tests with a stateful fake chain, 5 integration tests). Pure `src/core/trex/onboarding.py` decides the missing steps from `AccountState(identity, registered)` (including the inconsistent "registered without identity" case); `src/adapters/trex_onboard.py` reads `IdFactory.getIdentity` and `identity-registry.contains` and sends only what is missing: `IdFactory.createIdentity(wallet, salt=account name)` then `registerIdentity(wallet, identity, 124)` as Admin. `deploy` runs it as its last step and `python scripts/stack.py onboard` repeats it alone. On the real stack it worked first time; a second `onboard` printed nothing and the FireFly operation count did not change (also true for a second `deploy`). Admin stays unregistered and without an OnchainID, ready for Task 12. No idempotency keys are used here because every write is guarded by a state read.

### Task 10: Issue and add KYC claims so identities become verified

**Description:** Admin, through a `ClaimIssuer` listed in the TrustedIssuersRegistry, signs a KYC claim for each identity. Pure code in `src/core/trex/claims.py` builds the claim hash (`keccak256(abi.encode(identity, topic, data))`) and signs it with Admin's key (`eth-account`, already a dependency), checked against a known test vector. The identity owner (`anson`, `beatrice`, whose FireFly keys exist) then calls `addClaim` on their own OnchainID through FireFly. Skip a claim if `isVerified` is already true.

**Acceptance criteria:**
- [x] `isVerified` is true for Anson and Beatrice and false for Admin after the step
- [x] The claim signature is accepted by the ClaimIssuer on-chain (`isClaimValid` true), and a signature from any other key is rejected (tested)
- [x] Re-running sends no write, as in Task 9

**Verification:**
- [x] Tests pass: `pytest tests/unit` and `pytest -m integration -k onboarding_claim`
- [x] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 9

**Files likely touched:**
- `src/core/trex/claims.py`, `src/adapters/trex_onboard.py`
- `tests/unit/core/test_claims.py`, `tests/integration/test_onboarding.py`

**Size:** M

**Status:** Done 2026-10-02. Test-first (pure `src/core/trex/claims.py`: the claim hash checked against a hand-built ABI encoding, signature recovery, skip rule; adapter `issue_claims` with a stateful fake; 4 integration tests). Admin signs, the investor adds the claim to their own identity with their own FireFly key. On the real stack it worked first time, `isVerified` is true for Anson and Beatrice and false for Admin, the ClaimIssuer accepts the stored claim and Admin's signature and rejects one signed by Beatrice's key, and a second `onboard` sends nothing. `eth-abi` and `eth-utils`, which `eth-account` already installs, are now declared in `pyproject.toml` because the code imports them directly. **Resilience added after a real failure:** one cold `deploy` hit `HTTP 500 ... context deadline exceeded` (FireFly timed out waiting for evmconnect after 30 s, then completed the transaction itself). `submit` (in `trex_deploy.py`, also used by the onboarding writes) now retries a transient error under the same idempotency key, waits for an accepted earlier transaction to become final and takes the address from its operation output (so a succeeded earlier deploy no longer asks for `reset`), and retries under a new key only if it failed. Unit-tested; the timeout did not recur in three further cold `deploy` runs (51 to 72 s, no errors), so the live retry path is untested.

### Task 11: Mint to Anson and a compliant transfer to Beatrice

**Description:** Complete onboarding and add the first compliant transfer: after Tasks 9 and 10, mint 1000 `COIN` to Anson as Admin (through the contract API, waiting for the final status), then transfer 25 from Anson to Beatrice as the `anson` key. Mint is skipped if Anson already holds the target amount.

**Acceptance criteria:**
- [ ] After onboarding: Anson 1000, Beatrice 0, both verified (DL-2.4)
- [ ] After the transfer: Anson 975, Beatrice 25 (both balances change by the amount)
- [ ] Re-running onboarding sends no redundant mint, register or claim

**Verification:**
- [ ] Tests pass: `pytest -m integration -k "onboarding or transfer"`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 10

**Files likely touched:**
- `src/adapters/trex_onboard.py`, `src/core/trex/onboarding.py`
- `tests/integration/test_transfer.py`

**Size:** S

### Task 12: On-chain compliance rejection

**Description:** Prove the contract, not our code, refuses a transfer to an unverified recipient: `isVerified(admin)` is false, Anson sends 10 `COIN` to Admin through the contract API, and the operation ends `Failed` with a revert reason about the recipient. Record the real failed-status name and error text (spike Risk 7 gap) in `docs/spike-results.md`. Also repeat the call **directly through FireFly's contract API**, not through our client, and show the same revert. Balances are unchanged. The plan's anti-gate applies: if this does not actually revert, stop before Phase 3.

**Acceptance criteria:**
- [ ] The operation is `Failed` with a revert reason that names the unverified recipient, and Anson's and Admin's balances are unchanged
- [ ] The same revert appears through a plain HTTP call to FireFly's generated API (no project code in between)
- [ ] The observed failed-status value and revert text are recorded in `docs/spike-results.md`

**Verification:**
- [ ] Tests pass: `pytest -m integration -k compliance_rejection`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 11

**Files likely touched:**
- `tests/integration/test_compliance.py`
- `docs/spike-results.md`

**Size:** S

## Checkpoint: After Tasks 9–12

- [ ] `ruff check .`, `mypy .` and `pytest` clean
- [ ] Anson 1000 then 975, Beatrice 0 then 25, both verified; Admin unverified
- [ ] The rejection is a real revert, balances unchanged (plan anti-gate for Phase 3 not triggered)
- [ ] Re-running onboarding sends no redundant transaction
- [ ] Human review before proceeding

---

## Group D — Repeatability and close-out (plan step 7, DL-2.6)

### Task 13: `reset`, `up`, `deploy` repeatability

**Description:** Make the whole Phase 2 path repeatable from nothing: `python scripts/stack.py reset && python scripts/stack.py up && python scripts/stack.py deploy` (deploy includes registration, onboarding and the token) leaves a working `COIN`. `reset` also clears FireFly's Postgres and signer state (volumes) and removes a stale `deployed-addresses.json`. A session fixture runs `deploy` once per test session. Prove it three times in a row, with the whole `pytest -m integration` suite.

**Acceptance criteria:**
- [ ] After `reset`, no FireFly container or volume remains and no stale `deployed-addresses.json` or FireFly contract API exists
- [ ] `reset && up && deploy` followed by `pytest -m integration` passes in three consecutive runs
- [ ] A partial failure message of `deploy` names the step; running `deploy` again after fixing it completes (re-entrant)

**Verification:**
- [ ] Tests pass: `pytest -m integration` three times after `python scripts/stack.py reset && python scripts/stack.py up && python scripts/stack.py deploy`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 3, 11, 12

**Files likely touched:**
- `src/adapters/docker_stack.py`, `src/adapters/stack_cli.py`
- `tests/integration/conftest.py`, `tests/integration/test_reset.py`

**Size:** M

### Task 14: Phase 2 documentation and sign-off

**Description:** Update `README.md` Getting started (including `npm ci` in `contracts/` and `deploy`), mark DL-2.1 to DL-2.6 `Done` in `docs/deliverables.md` with the commands actually run, record the exit-gate results, mark Phase 2 complete in `docs/plan.md`, and verify the README from a fresh clone as in Phase 1.

**Acceptance criteria:**
- [ ] Following the README literally from a clean clone brings up the stack, deploys `COIN` and the integration tests pass
- [ ] `docs/deliverables.md` DL-2.1 to DL-2.6 are `Done` and their "How to try it" steps match the real commands and ports
- [ ] `docs/plan.md` Phase 2 is marked complete with the date

**Verification:**
- [ ] Tests pass: `pytest` and `pytest -m integration`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 1–13

**Files likely touched:**
- `README.md`, `docs/deliverables.md`, `docs/plan.md`, `PROJECT.md`

**Size:** XS

## Checkpoint: After Tasks 13–14 (Phase 2 exit gate)

- [ ] Integration tests (onboarding, transfer, rejection) pass
- [ ] Re-running register or claim sends no redundant transaction
- [ ] `reset && up && deploy` then `pytest -m integration` passes three times in a row
- [ ] `ruff check .`, `mypy .` and `pytest` clean
- [ ] Anti-gate from `docs/plan.md`: if the rejection does not revert, stop before Phase 3
- [ ] Human review before proceeding

---

## Open Questions

All answered by Howin on 2026-10-02 ("同意", as recommended in the last column).

| # | Question | Owner | Needed by | Decision |
|---|----------|-------|-----------|----------------|
| 1 | Contract artifacts: plan step 2 says "compile the T-REX suite with the EVM target from the spike". The official npm package ships compiled artifacts (0.8.17, no PUSH0, run at any fork, sizes already checked). Use them, or compile from source with Hardhat 3? | Howin | Task 5 | **Use the published artifacts** (no compiler, no Hardhat dependency). CLAUDE.md §12: reuse before writing. The "EVM target compatible" criterion in US-005 is met because they contain no Shanghai-only opcodes. Switch to Hardhat only if Task 5 finds a missing piece |
| 2 | Is `npm ci` in `contracts/` an accepted prerequisite for `deploy` (Node 24 is already listed in the README)? Alternative is vendoring the artifacts into the repo, which copies GPL-licensed T-REX and OnchainID output into it | Howin | Task 5 | **`npm ci` as a prerequisite**, `node_modules` gitignored. No licensed code copied |
| 3 | HTTP client for the FireFly adapter: standard library `urllib` or a new dependency (`httpx`, `requests`)? | Howin | Task 4 | **Standard library** (CLAUDE.md §12, and the tests already use it). Revisit in Phase 4 if the CLI needs more |
| 4 | Generate the signer keystores and FireFly config in `init` and commit them (demo keys, D-10)? | Howin | Task 1 | **Yes**, so a fresh clone needs no generation step, as for `network-config/` |
| 5 | Plan step 4 gate asks for a `mint` write through the generated API, but T-REX refuses `mint` to an unverified recipient, so it cannot be the first write. Use `unpause()` as the Task 8 write and prove `mint` in Task 11? | Howin | Task 8 | **Yes** (a paused token must be unpaused before any transfer anyway) |
| 6 | `deployed-addresses.json`: committed or gitignored? Addresses change on every reset | Howin | Task 6 | **Gitignored**, regenerated by `deploy` |
| 7 | Publish FireFly's admin/SPI port `5101`, or only HTTP `5000`? | Howin | Task 2 | **Only `5000`** (API, Swagger, Explorer). `5101` stays inside the network |
| 8 | Is onboarding part of `deploy` (one command, as in plan step 7 and DL-2.4 step 1) with a separate `onboard` command for re-running, or only inside `deploy`? | Howin | Task 9 | **Both**: `deploy` runs it, and `python scripts/stack.py onboard` repeats it alone |
| 9 | FireFly core image: the spike pinned the digest of the `latest` tag at generation time (a `v1.5.0` tag also exists). Keep the digest? | Howin | Task 2 | **Keep the digests from `docs/spike-results.md`** (exactly what was run) |

## Notes for review

- No task is sized L or larger. M: Tasks 1, 2, 4, 5, 6, 7, 8, 9, 10 and 13. Tasks 3, 11 and 12 are S, Task 14 is XS.
- No verification command is `TBD`; all come from `PROJECT.md`. The new `deploy` and `onboard` subcommands are created in Tasks 6 and 9.
- Highest risks are early: Task 5 (the full T-REX suite and its order, plan R3) and Task 7 (`deployTREXSuite` through FireFly). If either breaks D-04, stop and re-plan before Task 8.
- Out of scope for Phase 2: Paladin, the Python CLI and Caliper (plan §4 Phase 2 "Out of scope").
- Phase 2 needs about 5 to 8 days (plan). The integration suite grows to about 8 minutes once `deploy` is part of the session.
