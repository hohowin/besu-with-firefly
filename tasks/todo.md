# Tasks — Phase 4: Python CLI

> Source: `docs/plan.md` Phase 4 (steps 1 to 4, exit gate), `docs/prd.md` US-010, US-011, FR-9, FR-10, FR-12, `docs/deliverables.md` DL-4.1 and DL-4.2, `docs/use-cases.md` UC-05, UC-06, UC-11, `docs/architecture.md` §3 (failure handling), §5 (write lifecycle), §6 (per-module rationale). Decisions: D-06 (four commands: register, invoke, query, show tx/events; no Paladin). Phases 1 to 3 are complete; their lists are `tasks/phase-1-network.md`, `tasks/phase-2-firefly.md` and `tasks/phase-3-paladin.md` (Phase 3 was archived on 2026-10-03 with its three "human review" boxes still open, at Howin's choice).
> **Status: draft, waiting for Howin's approval. No implementation has started.**

## Overview

Phase 4 puts a small CLI over FireFly so a developer can drive the stack without `curl`: `register` (a contract interface and API), `invoke` (a write), `query` (a read) and `tx` (an operation and its events). Most of the FireFly plumbing already exists from Phase 2 (`src/adapters/firefly.py` has `api_invoke`, `api_query`, `ensure_interface`, `ensure_api`, `get_operation`, bounded polling, revert detection, and the request bodies are pure in `src/core/firefly/operations.py`). What is missing, and what this phase is really about, is:

1. a **core-owned port and error model**, so the dependency points the right way (today `FireflyError`, `Reverted` and `OperationTimeout` live in the adapter, and the `Protocol`s that describe FireFly sit in adapter files, which core cannot import);
2. a pure **outcome classification** (succeeded / failed / compliance revert / pending / unknown) that the CLI prints and the exit code follows, with the rule that **success is only ever printed for a `Succeeded` operation**;
3. a **CLI adapter** with no business logic, plain text and `--json` output, no colour, no prompts (PRD §6), so integration tests can assert on it.

Design choices that apply to every task:
- **Layers (`PROJECT.md`).** Pure logic and the port in `src/core/firefly/`; the existing FireFly client stays in `src/adapters/firefly.py` and implements the port; the CLI in a new `src/adapters/ff_cli.py` calls core only. `src/core/` gets no `print`, `input` or network call.
- **Reuse, don't rewrite (CLAUDE §12).** The client's behaviour does not change except that the error classes move to core and are re-exported by the adapter, so the 5 other adapter modules that import them keep working.
- **Command to endpoint.** Each command maps to one FireFly API call, as DL-4.1 requires: `query` is `POST /apis/{api}/query/{method}`, `invoke` is `POST /apis/{api}/invoke/{method}`, `tx` is `GET /operations/{id}` plus its events, and `register` is the existing interface and API registration.
- **Acting identity.** `--as NAME` resolves a wallet name from `network-config/wallets.json` (reusing `src/core/network/wallets.py`) and the output names it (architecture §7, "wrong identity" risk). Private keys are never printed.
- **Exit codes** (decided here, change in Open Questions if you disagree): `0` succeeded, `1` failed or reverted, `3` pending or unknown, `2` is left to `argparse` for usage errors.
- **Tests.** Unit tests mock the port and touch no network. Integration tests call the CLI's `main(argv)` against the live stack and keep using `tests/support/firefly.py` (its own helper, so a bug in the adapter cannot hide a bug in the stack). Integration order inside a run: they need `up` and `deploy` first.
- **Verification commands** (from `PROJECT.md`): `ruff check .`, `mypy .`, `pytest`, `pytest -m integration`.
- **Working branch:** `main`, committing per task (memory: no feature branches).

Sizes: no task is L or larger. Tasks 1, 2 and 3 are the largest (M).

---

## Group A — Core and the first command (plan steps 1 to 3 begin)

### Task 1: Core port, error model and outcome classification

**Description:** Add `src/core/firefly/port.py` (a `FireflyPort` `Protocol`: `api_query`, `api_invoke`, `get_operation`, `operation_events`, `ensure_interface`, `ensure_api`), `src/core/firefly/errors.py` (move `FireflyError`, `Reverted`, `OperationFailed`, `OperationTimeout`, `AlreadySubmitted` out of the adapter, unchanged) and `src/core/firefly/outcome.py`: a pure function that turns "what the port returned or raised" into one of `Succeeded`, `Failed(error)`, `ComplianceRevert(reason)` or `Pending(operation_id, tx)` (a timeout, a still-pending or an unrecognised status, or a transport error on a write, all of which are unknown and must carry whatever ids are known). `src/adapters/firefly.py` imports the errors from core and re-exports them, so existing imports still work.

**Acceptance criteria:**
- [ ] A `Succeeded` operation is the only input that classifies as `Succeeded`; `Pending`, `Initialized`, an empty or unknown status string, and `OperationTimeout` all classify as `Pending` (unit-tested, parametrised over statuses)
- [ ] A `Reverted` error classifies as `ComplianceRevert` with the contract's reason, and an `OperationFailed` as `Failed` with FireFly's error text
- [ ] `src/core/` contains no `print`, `input` or network call (checked by a test that scans the package source), and `FireflyClient` satisfies `FireflyPort` under `mypy`

**Verification:**
- [ ] Tests pass: `pytest tests/unit/core/test_firefly_outcome.py tests/unit/adapters/test_firefly.py tests/unit/adapters`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** None (Phases 1 to 3 done)

**Files likely touched:**
- `src/core/firefly/port.py`, `src/core/firefly/errors.py`, `src/core/firefly/outcome.py` (new)
- `src/adapters/firefly.py` (import and re-export the errors; add `operation_events` only in Task 3)
- `tests/unit/core/test_firefly_outcome.py` (new)

**Size:** M

### Task 2: CLI skeleton and `query` end to end

**Description:** Create the CLI adapter `src/adapters/ff_cli.py` with `main(argv)` (so tests can call it), a `query` subcommand (`query <method> --contract coin --input NAME=VALUE ...`), plain-text output by default and `--json`, and the console-script entry point in `pyproject.toml`. A pure core function parses `NAME=VALUE` inputs and resolves a wallet name given as a value to its address, and validates an address before anything is sent (architecture §8, input validation). FireFly unreachable exits non-zero with a transport error and no retry beyond the client's existing read retries (architecture §3). This is the riskiest task for the CLI shape (arguments, output, entry point), so it goes first.

**Acceptance criteria:**
- [ ] `query balanceOf --contract coin --input _userAddress=anson` against the live stack prints the balance as a number and exits 0; `--json` prints a JSON object with the same value
- [ ] A malformed address or unknown wallet name exits non-zero with a clear message and sends nothing (unit test with a port that fails on any call)
- [ ] FireFly down: non-zero exit, message names the transport error, no traceback

**Verification:**
- [ ] Tests pass: `pytest tests/unit` and `pytest -m integration tests/integration/test_cli_query.py`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 1

**Files likely touched:**
- `src/adapters/ff_cli.py` (new), `pyproject.toml` (`[project.scripts]`)
- `src/core/firefly/inputs.py` (new: parse and validate inputs)
- `tests/unit/core/test_firefly_inputs.py`, `tests/unit/adapters/test_ff_cli.py`, `tests/integration/test_cli_query.py` (new)

**Size:** M

### Task 3: `tx` command (operation and events)

**Description:** `tx <operation-id>` prints the operation's status, type, error text if any, its transaction id, and the events FireFly recorded for that transaction. First step: probe the live stack to find which FireFly endpoint returns useful events for a `blockchain_invoke` operation (candidates: `/transactions/{id}/blockchainevents`, `/transactions/{id}/status`, `/events?tx={id}`), because blockchain events only exist when a contract listener is registered, and Phase 2 registers none. Record the finding in `docs/spike-results.md` and pick the endpoint that needs no new listener; if only a listener gives events, stop and ask (Open Question 3). Add `operation_events` to the adapter, with tests against recorded response bodies (plan step 2 gate).

**Acceptance criteria:**
- [ ] `tx <operation-id>` for a succeeded transfer prints status `Succeeded`, the transaction id and at least one event line; for an unknown id it exits non-zero with FireFly's not-found text
- [ ] The adapter's `operation_events` is tested against a recorded real FireFly response (stored under `tests/unit/adapters/`), not an invented one
- [ ] The probe result and the chosen endpoint are written in `docs/spike-results.md` (a short Phase 4 section)

**Verification:**
- [ ] Tests pass: `pytest tests/unit/adapters/test_firefly.py` and `pytest -m integration tests/integration/test_cli_tx.py`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 2

**Files likely touched:**
- `src/adapters/firefly.py` (`operation_events`), `src/adapters/ff_cli.py` (`tx`)
- `src/core/firefly/outcome.py` or a small formatter in core for the status text
- `docs/spike-results.md`, `tests/unit/adapters/test_firefly.py`, `tests/integration/test_cli_tx.py`

**Size:** M

---

## Checkpoint: After Tasks 1–3

- [ ] `ruff check .`, `mypy .`, `pytest` all pass; `src/core/` has no `print`, `input` or network call
- [ ] `query` and `tx` run against the live stack and their output is asserted in integration tests
- [ ] The events endpoint question (Task 3) is settled, or escalated
- [ ] Human review before proceeding (**waiting for Howin**)

---

## Group B — Writes and the never-success-from-pending rule (plan steps 3 and 4)

### Task 4: `invoke` command with compliance transfer and rejection

**Description:** `invoke <method> --contract coin --as NAME --input NAME=VALUE ...` sends a write through the contract API, waits for the final operation, then prints the classified outcome from Task 1: success names the acting identity and the operation id (UC-06); a revert prints the contract's reason, exits 1 (UC-07). For the `transfer` example in the deliverables the CLI also prints the sender's and recipient's balances after a success and, on a rejection, confirms they are unchanged (read through the same port, so it is core orchestration, not CLI logic). The rejection is raised by the contract, not the CLI (PRD US-008): the CLI does no compliance check of its own.

**Acceptance criteria:**
- [ ] `invoke transfer --contract coin --as anson --input _to=beatrice --input _amount=<base units>` exits 0, prints the acting identity and operation id, and the balances change by the amount (integration)
- [ ] The same transfer to `admin` (unverified) exits 1, prints the contract's revert reason, and both balances are unchanged (integration, and equal to the revert seen by calling the contract API directly with `tests/support/firefly.py`)
- [ ] Unit tests with a mocked port cover: succeeded, failed, reverted, and that no private key or key file path appears in any output

**Verification:**
- [ ] Tests pass: `pytest tests/unit` and `pytest -m integration tests/integration/test_cli_invoke.py`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 1 and 2

**Files likely touched:**
- `src/adapters/ff_cli.py` (`invoke`), `src/core/firefly/invoke.py` (new: the orchestration and balance report)
- `tests/unit/core/test_firefly_invoke.py`, `tests/unit/adapters/test_ff_cli.py`, `tests/integration/test_cli_invoke.py` (new)

**Size:** M

### Task 5: Pending and unknown states never report success

**Description:** Make the UC-11 rule provable end to end. In the CLI, a `Pending` outcome prints "pending or unknown", the operation id and transaction id (when known), the hint to run `tx <id>` later, and exits 3. This covers: the write still pending after `--timeout`, a status string the code does not recognise, and a transport error or timeout **after a write was sent** (the write may or may not have been accepted, so it is unknown, not failed). The client's `_call` already turns `OSError` into `FireflyError`; this task separates "could not send" (safe to say failed) from "sent, no answer" (unknown) for writes. Add `--timeout` to `invoke`.

**Acceptance criteria:**
- [ ] Unit test `test_cli_never_reports_success_from_pending` (named in UC-11) drives the CLI with a fake port that returns pending forever, an unrecognised status, and a transport error after send: in every case the exit code is 3, stdout contains no "success"/"sent"/"succeeded" text, and the ids that are known are printed
- [ ] Integration: `invoke ... --timeout 0` (or the smallest accepted value) against the live stack exits 3 and prints the operation id, then `tx <id>` later reports the final status
- [ ] A transport error on a read still exits 1 (failed), not 3

**Verification:**
- [ ] Tests pass: `pytest tests/unit` and `pytest -m integration tests/integration/test_cli_pending.py`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Tasks 3 and 4

**Files likely touched:**
- `src/adapters/firefly.py` (distinguish send failure from no answer on writes), `src/core/firefly/outcome.py`
- `src/adapters/ff_cli.py` (`--timeout`, exit code 3)
- `tests/unit/core/test_firefly_outcome.py`, `tests/unit/adapters/test_firefly.py`, `tests/unit/adapters/test_ff_cli.py`, `tests/integration/test_cli_pending.py`

**Size:** M

### Task 6: `register` command

**Description:** `register --name NAME --abi PATH --address ADDRESS [--version V]` registers a contract interface from an ABI file (a raw ABI array or an artifact JSON with an `abi` key) and creates a contract API for the address, using the existing `ensure_interface` and `ensure_api`. Running it twice does nothing the second time and says so; an API of the same name pointing elsewhere is an error (the client already refuses). The new API is then usable by `query` and `invoke` through `--contract NAME`.

**Acceptance criteria:**
- [ ] `register --name coin-copy --abi <token abi> --address <deployed token>` exits 0, prints the interface and API ids, and `query name --contract coin-copy` returns `Coin` (integration)
- [ ] The second run exits 0 and prints "already registered" with no new registration; a different address under the same name exits non-zero with the client's message (unit, mocked port)
- [ ] A missing or malformed ABI file exits non-zero before any FireFly call

**Verification:**
- [ ] Tests pass: `pytest tests/unit` and `pytest -m integration tests/integration/test_cli_register.py`
- [ ] Checks clean: `ruff check .` and `mypy .`

**Dependencies:** Task 2

**Files likely touched:**
- `src/adapters/ff_cli.py` (`register`), `src/core/firefly/abi.py` (new: read the ABI shapes, pure on parsed JSON)
- `tests/unit/core/test_firefly_abi.py`, `tests/unit/adapters/test_ff_cli.py`, `tests/integration/test_cli_register.py` (new)

**Size:** S

---

## Checkpoint: After Tasks 4–6

- [ ] `ruff check .`, `mypy .`, `pytest` all pass
- [ ] The DL-4.1 "how to try it" steps 1 to 4 run as written against the live stack (command names as decided in Open Question 1)
- [ ] The pending/unknown test exists, passes, and fails when the rule is deliberately broken (mutation check done once by hand)
- [ ] Human review before proceeding (**waiting for Howin**)

---

## Group C — Exit gate and documentation (Phase 4 exit gate, DL-4.1 and DL-4.2)

### Task 7: Repeatability and Phase 4 documentation

**Description:** Prove the full integration suite, including the new CLI tests, passes on 3 consecutive fresh stacks: `python scripts/stack.py reset && python scripts/stack.py up && python scripts/stack.py deploy && pytest -m integration`, three times (about 13 minutes each). Fix the cause of any flaky test rather than rerunning (plan anti-gate). Then update `README.md` (the CLI commands and the `pip install -e ".[dev]"` re-run for the entry point), `PROJECT.md` (commands table and directory layout: `src/core/firefly/`, `ff_cli.py`), `docs/deliverables.md` (DL-4.1 and DL-4.2 set to `Done`, with commands that were actually run and their real output), `docs/plan.md` (Phase 4 status with the date and exact result, exit gate boxes) and `docs/prd.md` (US-010 and US-011 boxes only where proved).

**Acceptance criteria:**
- [ ] 3 consecutive fresh-stack runs of `pytest -m integration` pass, with the three outputs recorded in the plan note; no test is marked flaky, and none is skipped without a reason
- [ ] `ruff check .`, `mypy .` and `pytest` (offline) pass
- [ ] DL-4.1 and DL-4.2 are `Done` with commands that were run; `docs/plan.md` marks Phase 4 with the date and result

**Verification:**
- [ ] Tests pass: the 3-run loop above
- [ ] Checks clean: `ruff check .` and `mypy .`; README steps verified from a fresh clone (as in Phase 3)

**Dependencies:** Tasks 1 to 6

**Files likely touched:**
- `README.md`, `PROJECT.md`, `docs/deliverables.md`, `docs/plan.md`, `docs/prd.md`

**Size:** S

---

## Checkpoint: After Task 7 (Phase 4 exit gate)

- [ ] All DL-4.x deliverables verified
- [ ] `ruff check .`, `mypy .`, `pytest` all pass
- [ ] Integration tests pass across 3 consecutive fresh-stack runs
- [ ] Human review of the Phase 4 exit gate (**waiting for Howin**)

---

## Open Questions

| # | Question | Owner | Recommended default |
|---|---|---|---|
| 1 | CLI name and entry point. DL-4.1 plans `besu-ff` (a console script, so `pip install -e ".[dev]"` must be re-run), while `stack.py` is run as `python scripts/stack.py`. | Howin | Console script `besu-ff` in `pyproject.toml`, as DL-4.1 says; tests call `main(argv)` directly |
| 2 | Argument style. DL-4.1 shows `invoke transfer --to ADDR --amount 25` (friendly flags, coins), but D-06 and PRD §6 want one FireFly endpoint behind each command and no per-method special cases. | Howin | Generic `--input NAME=VALUE` (wallet names resolve to addresses; amounts in base units), and update the DL-4.1 examples to match. Per-method flags (`--to`, `--amount` in coins) would put contract-specific logic in the CLI |
| 3 | `tx` events. Blockchain events only appear in FireFly when a contract listener is registered, and none is today. If Task 3's probe finds no usable events without one, should Phase 4 add a listener (a new write at `deploy`) or show only FireFly's own transaction and operation records? | Howin | Show operations and FireFly's transaction events only; a listener is out of scope for the MVP |
| 4 | Exit code for pending/unknown. `argparse` already uses 2 for usage errors. | Howin | `3` for pending or unknown, `1` for failed or reverted, as in the Overview |
| 5 | Idempotency (plan Q7, UC-11 notes). Should `invoke` send an idempotency key so a retry after "unknown" cannot double-send? It adds a flag and output beyond the four commands. | Howin | Not in Phase 4. Print the operation and transaction ids so the developer can check with `tx`; revisit if a retry ever double-sends |
| 6 | Phase 3's three "human review" boxes (`tasks/phase-3-paladin.md`, lines 191, 297, 359) are still open. Do they need ticking before Phase 4 starts? | Howin | Tick them (the exit gate was verified in `a21c399`) when convenient; nothing in Phase 4 depends on them |

## Notes

- Out of scope (plan §4 Phase 4): Paladin commands (FR-18), a web UI, a contract listener, anything beyond the four commands. Phase 5 adds `perf/`.
- No task is XL. No `TBD` verification commands: every command above is in `PROJECT.md`.
- Phase 4 is about 3 to 5 days (plan).
