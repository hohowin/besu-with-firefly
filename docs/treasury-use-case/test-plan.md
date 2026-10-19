# Test plan: Treasury branch funding

> Companion docs: [prd.md](prd.md) · [use-case.md](use-case.md) · [design.md](design.md) · [tasks.md](tasks.md)
> Follows `PROJECT.md`: unit tests mock the port and touch no network; integration tests need the live stack; the tests mirror the code.

## 1. Strategy

| Layer | Tool | What it proves | Needs Docker |
|---|---|---|---|
| Core unit | `pytest` | Money, FX, dates, state machine, ids, conservation | no |
| Adapter unit | `pytest` with a fake `FireflyPort` | The right API, signer, idempotency key; service decisions; HTTP status codes | no |
| Contract | contract test runner (Task 4 and 5) | Every rule and revert in `FundingRequest` and `CurrencyToken` | no (or the live chain) |
| Integration | `pytest -m integration` | The whole flow on the real chain through FireFly | yes |
| Browser | Playwright | The page works and escapes text | yes |

The most important rule: **negative tests call the contract API directly**, not through the UI, so they prove the chain is the authorization boundary (TD-09).

## 2. Invariants (checked after every step of every integration test)

| ID | Invariant |
|---|---|
| I1 | `CADC.totalSupply` = sum of `amountCad` over requests in `Approved` |
| I2 | `GBPC.totalSupply` = sum of `amountGbp` over requests in `Settled` |
| I3 | `treasury` CADC balance = `CADC.totalSupply`; `ldn` GBPC balance = `GBPC.totalSupply` |
| I4 | A request never has both CADC outstanding and GBPC outstanding |
| I5 | `amountGbp` = floor(`amountCad` × `ratePpm` / 1,000,000) for every `Settled` or `Redeemed` request |
| I6 | The number of events per request equals its path (`Requested`, then `Approved`, `Settled`, `Redeemed`; or `Requested`, `Rejected`) |

## 3. Test cases

### 3.1 Unit: core (Tasks 1 to 3)

| Test | Input | Expected |
|---|---|---|
| `test_parse_amount_valid` | `"1000.00"`, `"0.01"`, `"1000"` | 100000, 1, 100000 |
| `test_parse_amount_invalid` | `"0"`, `"-1"`, `"1000.001"`, `"1,000"`, `"1e3"`, `""`, `"abc"`, above cap | specific error each |
| `test_convert_floor` | (100000, 580000), (10001, 580000), (1, 580000) | 58000, 5800, error (zero) |
| `test_fx_lookup_order` | table with a date and a default | date wins; no date falls to default; neither raises `FxRateMissing` |
| `test_fx_rate_format` | `"0.58"`, `"0.5800001"`, `"-0.5"`, `"x"` | 580000 ok; the last three rejected |
| `test_processing_date_zone` | 2026-10-18T22:30Z; the DST change days | `20261018` London; `20261019` Tokyo; correct on both DST days |
| `test_transition_table` | all state and action pairs | only the 5 legal ones allowed |
| `test_idempotency_key` | id, action | `<id>:<action>`; different actions differ |
| `test_conservation_detects_drift` | supply off by 1 | error |
| `test_core_has_no_io` | scan package source | no `print`, `input`, `open`, `float`, network import |

### 3.2 Unit: adapters (Tasks 7 to 9)

| Test | Expected |
|---|---|
| `test_gateway_calls` | `create` uses signer `ldn`, `approve` `tor`, `settle` `treasury`, `redeem` `ldn`, and each key `<id>:<action>` |
| `test_gateway_duplicate_returns_first_operation` | 409 `FF10431` handled, no exception |
| `test_service_settles_once` | `Approved` + rate: one `settle`, then one `redeem`; a second sweep sends nothing |
| `test_service_missing_rate_blocks` | stays `Approved`, reason is `FX rate missing for <date>` |
| `test_service_pending_not_success` | `Pending` is reported as pending and not repeated |
| `test_http_status_codes` | 202, 400, 409, 502 as in design §7 |
| `test_http_no_secrets` | no private key or password in any body or log |
| `test_http_loopback_only` | refuses a non-loopback bind by default |

### 3.3 Contract (Task 5)

| Test | Expected |
|---|---|
| `test_create_rules` | non-requester → `NotRequester`; duplicate id → `Exists`; 0 or above cap → `BadAmount`; bad date → `BadDate` |
| `test_approve_rules` | non-approver → `NotApprover`; requester → `SelfApproval`; wrong state → `BadState`; success mints CADC to treasury |
| `test_reject_rules` | reason of 141 chars → `ReasonTooLong`; no token minted |
| `test_settle_rules` | non-treasury → `NotTreasury`; rate 0, below min or above max → `BadRate`; wrong state → `BadState`; tiny amount rounding to 0 → `BadAmount` |
| `test_settle_effect` | CADC burned, GBPC minted to requester, `Settled` event carries cad, gbp, rate |
| `test_redeem_rules` | not the beneficiary → `NotBeneficiary`; before settle → `BadState`; twice → `BadState` |
| `test_token_controller` | only `FundingRequest` can `mint` and `burn`; admin cannot; controller set once |
| `test_property_conservation` | random sequences of legal calls keep I1 to I5 |

### 3.4 Integration (Task 11), `tests/integration/test_treasury_*.py`

| Test | Covers | Steps and expected result |
|---|---|---|
| `test_treasury_deploy_is_idempotent` | UC-T5, TR-US-06 | Run `treasury` twice; second run sends no transaction; addresses non-zero |
| `test_funding_happy_path` | UC-T1, TR-US-01 to 04 | `ldn` creates 1000.00; `tor` approves; CADC 100000 at treasury; settle at 0.580000; GBPC 58000 to `ldn`; redeem; all supplies 0; state `Redeemed`; events match; under 60 s; I1 to I6 after each step |
| `test_reject_mints_nothing` | UC-T2 | reject; both supplies 0; state `Rejected`; reason in event |
| `test_self_approval_reverts` | F2 | `ldn` approves own request through the contract API; revert `SelfApproval`; state `Requested` |
| `test_non_approver_reverts` | F2 | `treasury` approves; revert `NotApprover` |
| `test_double_approve_reverts` | F3 | approve twice; second reverts `BadState`; CADC minted once |
| `test_settle_before_approve_reverts` | F3 | revert `BadState` |
| `test_wrong_wallet_settle_reverts` | F9 | `tor` calls settle; `NotTreasury` |
| `test_redeem_by_other_reverts` | F10 | `tor` redeems; `NotBeneficiary` |
| `test_missing_fx_rate_blocks_then_recovers` | F6 | remove rate and default; approve; request stays `Approved`, CADC at treasury; add rate; retry settle; reaches `Redeemed` |
| `test_dated_rate_beats_default` | TR-US-03 | two requests, one date with its own rate; GBP amounts use the right ones |
| `test_idempotent_retry` | F4 | send the same create twice; one request, API answers with the first operation |
| `test_restart_recovery` | F8 | approve, stop the app before settle, start it; the request settles once |
| `test_pending_is_not_success` | F5 | with a very short poll window the API returns `Pending`, later reads show `Succeeded` |
| `test_ledger_matches_chain` | UC-T4, TR-US-05 | Ledger numbers equal independent reads through `tests/support/firefly.py` |
| `test_amount_validation_in_ui_api` | F1 | bad amounts get 400 and no transaction is sent (block count unchanged) |

### 3.5 Browser (Task 10)

| Test | Expected |
|---|---|
| `test_ui_happy_path` | LDN tab submits; TOR tab approves; Ledger shows `Redeemed`, 1000.00 CAD, 0.580000, 580.00 GBP |
| `test_ui_escapes_text` | reject reason `<img src=x onerror=alert(1)>` renders as text, no dialog opens |
| `test_ui_disables_buttons_while_pending` | the button is disabled during the call |

## 4. Traceability

| Requirement | Tests |
|---|---|
| TR-US-01 | parse tests, `test_funding_happy_path`, `test_idempotent_retry`, `test_amount_validation_in_ui_api` |
| TR-US-02 | `test_approve_rules`, `test_reject_mints_nothing`, `test_self_approval_reverts`, `test_non_approver_reverts`, `test_double_approve_reverts` |
| TR-US-03 | `test_fx_lookup_order`, `test_convert_floor`, `test_settle_effect`, `test_missing_fx_rate_blocks_then_recovers`, `test_restart_recovery` |
| TR-US-04 | `test_redeem_rules`, `test_redeem_by_other_reverts`, `test_funding_happy_path` |
| TR-US-05 | `test_ledger_matches_chain`, `test_ui_happy_path` |
| TR-US-06 | `test_treasury_deploy_is_idempotent` |
| TR-NFR-01 | `test_core_has_no_io` (no `float`) |
| TR-NFR-02 | invariants I1 to I6, `test_property_conservation` |
| TR-NFR-03 | the five contract-API negative tests |
| TR-NFR-04 | `test_idempotent_retry`, `test_restart_recovery` |
| TR-NFR-05 | the timer in `test_funding_happy_path` |
| TR-NFR-06 | log assertions in `test_service_*` |

## 5. Exit criteria

- All tests above pass; `ruff check .` and `mypy .` are clean
- `pytest -m integration` passes three times in a row from `reset`, with the existing 54 tests included
- No test weakened or skipped to get there (CLAUDE §12)
