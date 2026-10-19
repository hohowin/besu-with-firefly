# PRD: Treasury branch funding

> Companion docs: [README.md](README.md) · [use-case.md](use-case.md) · [design.md](design.md) · [tasks.md](tasks.md) · [test-plan.md](test-plan.md)
> Project PRD: `docs/prd.md`. IDs here are `TR-US-xx`, `TR-FR-xx`, `TR-NFR-xx` so they do not collide.

## 1. Overview

A company has branches in different countries and one shared platform: **one Besu RPC node, one FireFly and one UI**. A branch asks for funding in its parent currency, another branch approves, and the treasury converts the money to the requesting branch's currency. The first scenario is London (GBP) asking Toronto (CAD) for CAD 1,000.00. This PRD adds the flow to the existing local demo network. It is a demo: no real money, no real FX feed, localhost only.

**Domain vocabulary:**
- `funding request` — an on-chain record: requester, amount in CAD, processing date, state
- `CADC`, `GBPC` — the two currency tokens (1 unit = 0.01 of the currency, 2 decimals)
- `processing date` — the requester's local calendar date (Europe/London for LDN), fixed at creation
- `treasury wallet` — the wallet that holds CADC between approval and settlement
- `settle` — burn the CADC, mint the GBPC, record the rate
- `redeem` — the beneficiary burns its GBPC, meaning the money is paid out off-chain
- `maker-checker` — the requester and the approver must be different wallets

## 2. Goals

- A LDN user submits a CAD funding request in a UI; a TOR user approves it in the same UI
- Approval mints CADC; settlement burns it and mints GBPC at a recorded fixed rate; redemption burns the GBPC
- Every state change is a FireFly-driven transaction; the chain, not the UI, enforces who may do what
- The amount, rate, dates and transaction ids of each request can be reconstructed from the chain alone
- It runs on the existing network with no change to `COIN`, Paladin or the 54 existing integration tests

## 3. Non-goals

- Real FX feeds, FX oracles, rate history, spreads or fees
- User login, passwords, SSO (TD-09)
- More than the CAD to GBP pair and the LDN and TOR branches (the design allows more, the build does not)
- Multi-RPC-node or multi-FireFly setups; per-branch UIs
- Compliance checks on token holders (no T-REX identity for CADC or GBPC)
- Privacy between branches (everything is on the public demo ledger; Paladin Noto is a possible later variant)
- Persistence beyond the chain: the app keeps no database (plan D-11)

## 4. User stories

### TR-US-01: LDN creates a funding request
**As** an LDN user, **I want** to enter a CAD amount and submit it, **so that** the Toronto branch can fund us.

**Acceptance criteria:**
- [ ] The form takes one amount in CAD (2 decimals) and shows the processing date (today in Europe/London) read-only
- [ ] Zero, negative, non-numeric, more than 2 decimals, and above the cap (default CAD 1,000,000.00) are rejected before any transaction is sent
- [ ] A valid submission creates a request in state `Requested` and shows its id
- [ ] Submitting the same form twice (double click, retry) creates one request

### TR-US-02: TOR approves or rejects
**As** a TOR user, **I want** to see requests waiting for approval and approve or reject them, **so that** money moves only with a second person's consent.

**Acceptance criteria:**
- [ ] The pending list shows id, requester branch, CAD amount and processing date
- [ ] Approve moves the request to `Approved` and mints exactly the requested CADC to the treasury wallet in the same transaction
- [ ] Reject takes a reason (max 140 characters), moves the request to `Rejected`, mints nothing
- [ ] The requester cannot approve or reject their own request; a wallet without the approver role cannot either (the transaction reverts)
- [ ] A request can be approved or rejected only once

### TR-US-03: The treasury converts CAD to GBP
**As** the treasury, **I want** an approved request converted at the configured rate, **so that** LDN receives GBP.

**Acceptance criteria:**
- [ ] When a request is `Approved` the service reads the CAD to GBP rate for the processing date (dated entry first, then `default`) and calls `settle`
- [ ] `settle` burns the CADC, mints GBPC to the requester's wallet and stores the CAD amount, GBP amount and rate in the request and in the `Settled` event, in one transaction
- [ ] GBP = floor(CAD minor units × rate / 1,000,000); the worked example 100000 × 0.580000 gives 58000
- [ ] A missing rate leaves the request `Approved`, shows the reason, and settles after the rate is added and the user presses retry
- [ ] After an app restart, requests left `Approved` are settled, once

### TR-US-04: LDN redeems
**As** an LDN user, **I want** the GBP received and then burned, **so that** the on-chain balance goes back to zero when the money is paid out.

**Acceptance criteria:**
- [ ] After `Settled`, the `ldn` wallet's `redeem` burns the full GBPC amount of that request and moves the state to `Redeemed`
- [ ] Only the beneficiary can redeem; only once; only after `Settled`

### TR-US-05: See the whole picture
**As** an auditor or developer, **I want** one view of every request and all balances, **so that** I can check the books.

**Acceptance criteria:**
- [ ] A Ledger view lists every request with state, amounts, rate, processing date and the transaction ids
- [ ] It shows CADC and GBPC balances for `ldn`, `tor`, `treasury` and the two total supplies
- [ ] The values are read from the chain, not from app memory

### TR-US-06: Set up and reset the demo
**As** a developer, **I want** one idempotent command to add the treasury pieces, **so that** the demo is repeatable.

**Acceptance criteria:**
- [ ] `python scripts/stack.py treasury` adds the three wallets, deploys the contracts through FireFly, registers interfaces and APIs, grants roles, and writes the addresses into `deployed-addresses.json`
- [ ] A second run changes nothing
- [ ] `reset` removes the treasury pieces together with everything else

## 5. Functional requirements

- TR-FR-01: `FundingRequest` has the states `Requested`, `Approved`, `Rejected`, `Settled`, `Redeemed`, and allows only the transitions in [use-case.md](use-case.md). (US-01 to US-04)
- TR-FR-02: `createRequest(id, amountCad, processingDate)` is callable only by a wallet with the requester role; the caller becomes the beneficiary; `id` must be unused. (US-01)
- TR-FR-03: `approve(id)` and `reject(id, reason)` are callable only by an approver who is not the requester. `approve` mints CADC to the treasury wallet in the same transaction. (US-02)
- TR-FR-04: `settle(id, ratePpm)` is callable only by the treasury wallet, `ratePpm` > 0. It burns the CADC from the treasury wallet and mints GBPC to the beneficiary in one transaction. (US-03)
- TR-FR-05: `redeem(id)` is callable only by the beneficiary and burns the GBPC of that request. (US-04)
- TR-FR-06: `CADC` and `GBPC` can be minted and burned only by `FundingRequest`; nobody else, including the admin, can mint. (US-02 to US-04)
- TR-FR-07: The contract keeps an enumerable list of request ids and a getter per id, so the UI needs no database. (US-05)
- TR-FR-08: Every write goes through the FireFly contract API with `idempotencyKey = <requestId>:<action>`. Success is shown only for an operation with status `Succeeded`. (US-01 to US-04)
- TR-FR-09: Pure logic (amount parsing, FX lookup and conversion, processing-date, validation, outcome classification) is in `src/core/treasury/` and does no I/O. (all)
- TR-FR-10: The UI process holds no private keys; signing is done by FireFly's signer for the wallet named in the request. (all)
- TR-FR-11: The FX table is a file (`network-config/treasury/fx-rates.json`) read at settlement time, so a change needs no restart. (US-03)
- TR-FR-12: The UI offers: create, pending list, approve, reject, retry settle, my requests, Ledger. (US-01 to US-05)

## 6. Non-functional requirements

| ID | Quality | Requirement | How it is checked |
|---|---|---|---|
| TR-NFR-01 | Correctness | Money is integer minor units end to end; no floating point anywhere | unit test scans core for `float` |
| TR-NFR-02 | Correctness | Conservation: after every step, `CADC supply` = sum of CAD of `Approved` requests, and `GBPC supply` = sum of GBP of `Settled` requests | integration invariant test |
| TR-NFR-03 | Security | Authorization is enforced by the contracts, not the UI. The UI "act as" selector is a demo convenience | negative tests call the contract API directly |
| TR-NFR-04 | Availability | Any step can be retried safely; after a crash no step is lost or doubled | restart test, idempotency test |
| TR-NFR-05 | Performance | Create to `Redeemed` on the local stack in under 60 s (the chain makes a block every 2 s and FireFly confirms each write) | timed in the happy-path test, a budget, not a benchmark |
| TR-NFR-06 | Observability | Every log line for a request carries `requestId`, `action`, `operationId`; an error says which step failed and what state the request is in | log assertions in unit tests |
| TR-NFR-07 | Scalability | Out of scope; the list getter is O(n) and is fine for a demo (see design risk R5) | n/a |
| TR-NFR-08 | Cost | No new paid or hosted service; one new npm dev package (`solc`, pinned) if approved (Q5) | review |

## 7. Success metrics

- `pytest -m integration` for the treasury tests passes 3 times in a row from `reset`, as D-17 did for the rest
- The existing 54 integration tests still pass
- `ruff check .` and `mypy .` are clean
- The conservation invariant holds after every step of every treasury test

## 8. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | The repo has never compiled its own Solidity; the toolchain and EVM target (D-08, Shanghai) could cause trouble | Medium | Medium | Task 4 is a small spike-style task first; fallback: write the contract with the smallest feature set |
| R2 | A rate is passed in by the treasury wallet, so a bad rate mints the wrong GBP | Medium | High in real life, none in a demo | Contract bounds the rate (`min`, `max` set at deploy); every rate is in the event; an oracle contract is the documented next step |
| R3 | Scope creep: this is the first web UI in the repo | High | Medium | Keep the UI to one static page and a JSON API; no framework |
| R4 | Auto-settle and auto-redeem hide the human steps in step 6 and 7 | Medium | Low | UI shows each step as its own line item with timestamp |
| R5 | Listing requests reads one by one | Low | Low | Fine for tens of requests; add pagination if it grows |

## 9. Open Questions

Each has a recommended answer. I proceed with the recommendation in [design.md](design.md) unless you say otherwise.

| # | Question | Recommendation | Status |
|---|---|---|---|
| Q1 | Does "approve" mint CAD to the **treasury wallet**, or to the LDN wallet first? | Treasury wallet. LDN never holds CADC; the CAD is a short-lived claim the treasury converts | Open |
| Q2 | Step 7: is the burn an LDN user's action (a button) or automatic? | Automatic after settlement, signed as `ldn`. A button is a one-line UI change if you prefer it | Open |
| Q3 | Rounding of GBP: down, half-up or half-even? | Down (floor). It is the simplest to prove (the rounding dust is always less than one penny and never created from nothing). Finance may want half-up | Open |
| Q4 | FX rate lookup when the processing date has no entry: stop, or use `default`? | Dated entry, then `default`, then stop. The `default` is flagged in the UI | Open |
| Q5 | May the repo take a pinned `solc` npm package in `contracts/` (not global)? | Yes. Compile once, commit the artifacts and `SHA256SUMS`, like `contracts/paladin/` | Open |
| Q6 | UI technology: stdlib `http.server` plus one HTML page, or FastAPI plus uvicorn? | Stdlib (CLAUDE §12: stdlib before new dependencies). FastAPI is a clean swap later because handlers are sync either way | Open |
| Q7 | Must the approver be from a different branch than the requester, or only a different wallet? | Different wallet, with the approver role. Branch is a label in the event | Open |
| Q8 | Is the amount cap CAD 1,000,000.00 per request acceptable as a default? | Yes, configurable | Open |
| Q9 | Should `docker compose up` also deploy the treasury pieces (like `deployer` does for T-REX)? | Not in v1. Keep `stack.py treasury` separate so Phase 6 is untouched | Open |
