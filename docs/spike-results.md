# Spike Results — Phase 0

> **Status: in progress (3 of 6 risks answered).** Started 2026-10-01. Deliverable DL-0.2 in `docs/deliverables.md`. Evidence labelled **run** was observed on a live container. **read** means taken from generated files or tool output. Throwaway spike files are in `spike/`.

## Environment (checked 2026-10-01)

| Item | Result |
|---|---|
| OS / Docker | Windows 11, Docker Desktop (engine 29.5.2), 12 CPUs, about 16 GB RAM |
| Node / npm / Python / Go | v24.11.1 / 11.6.2 / 3.13.3 / 1.27.0 |
| `make` | **Not installed.** The planned `make up` / `make deploy` / `make reset` do not work on this machine as written |
| `ff` (FireFly CLI) | v1.5.0, built locally with `go install github.com/hyperledger-firefly/cli/ff@v1.5.0` (no Windows release exists; the old module path `hyperledger/firefly-cli` fails). Binary: `C:\Users\ho1ho\go\bin\ff.exe` |
| Host ports | 5432 is used by a local Postgres. The spike publishes nothing on 5432 |

## Verdicts

| # | Risk | Verdict | Fallback if it had failed |
|---|---|---|---|
| 1 | FireFly on an external Besu, evmconnect on a zero-gas chain | **Feasible** (run) | FireFly's own Clique chain for FireFly only |
| 3 | T-REX through FireFly's deploy API, contract size | **Feasible for size and a first deploy** (run). Full suite deploy is a Phase 2 task | Trim the suite, record as a change to D-04 |
| 4 | EVM fork level (D-08) | **Shanghai confirmed working** (run). Paladin's own need is still unknown | Revise D-08 |
| 7 | FireFly invoke idempotency and status names | **Answered** (run) | `core` checks state before every write |
| 2 | Paladin hand-written config on external Besu, Noto | **Not started** | Paladin on `kind` (not its own devnet Besu) |
| 5 | Caliper Besu connector and Node version | **Not started** | Custom workload or another load tool |

## Risk 1 — FireFly on an external Besu: feasible

**What was run:**
1. `hyperledger/besu:26.8.1`, one QBFT validator, genesis generated with `besu operator generate-blockchain-config`, fork settings `berlinBlock 0`, `londonBlock 0`, `zeroBaseFee true`, `shanghaiTime 0`, chainId `20260916`, block period 2s. Result: a block every 2 seconds, `eth_gasPrice` returns `0x0`, `qbft_getValidatorsByBlockNumber` returns the one validator. (run)
2. FireFly **gateway mode** (`multiparty.enabled: false`) in a hand-written Compose with **4 containers**: Postgres, FireFly signer, evmconnect, FireFly core. Config derived from what `ff init` generates. FireFly reaches Besu through the signer, whose backend is `http://host.docker.internal:8545`. `GET /api/v1/status` returns the `default` namespace with the `ethereum` blockchain plugin and `multiparty.enabled: false`. (run)
3. **Deploy through FireFly:** `POST /api/v1/namespaces/default/contracts/deploy?confirm=true` with `{contract, definition, input, key}` returned HTTP 200, `"status":"Succeeded"`, `type: blockchain_deploy`, and a contract address. `eth_getCode` on that address returns code. (run)
4. **Invoke and query:** `POST /contracts/invoke?confirm=true` as the `anson` key returned `Succeeded`. `POST /contracts/query` returned `{"output":"42"}`. Two different keys (admin to deploy, anson to invoke) both signed, so a multi-key keystore works. (run)

**Config facts that matter (read, then confirmed by the run above):**
- evmconnect needs `policyengine.simple.fixedGasPrice: 0`, `gasOracle.mode: fixed`, `confirmations.required: 0`. This is what makes it work on a zero-gas QBFT chain.
- The signer reads its config from `/etc/firefly/firefly.ffsigner.yaml`. A different file name makes the container exit with `FF00101: Failed to read config`.
- The signer keystore is a directory with, per key, an Ethereum keystore JSON named by address, a `.toml` pointing at it, plus a shared `password` file. Adding keys is just adding files; demo wallets were generated with `ethers` v6.
- FireFly core needs a hand-written `namespaces` block for gateway mode. `ff init` writes `namespaces: null`. The working block has `default: default`, a predefined namespace with `defaultKey`, `plugins: [database0, blockchain0]` and `multiparty.enabled: false`.
- **Data exchange and IPFS are not needed in gateway mode.** `ff init` still generates them, but the hand-written 4-container stack ran fine without them. This matches `docs/architecture.md`.
- The pinned images used: FireFly core `ghcr.io/hyperledger-firefly/firefly@sha256:d321bcd8c567...` (`latest` at generation time), evmconnect v1.5.1 (`@sha256:ca6e3860c784...`), signer v1.2.1 (`@sha256:412236dfab0c...`), `postgres:16-alpine`.

**Findings about `ff` itself:**
- `ff init ethereum -n besu --consensus qbft` fails with `currently only Clique consensus is supported`. This confirms D-03.
- `ff init ethereum -n remote-rpc --remote-node-url URL --multiparty=false -d postgres -t none` works at init time.
- **`ff start` does not work on this setup.** It fails with `dial tcp 127.0.0.1:5100: connectex: ... refused` before any container exists, with or without `--no-rollback`. The root cause was not found. It was not needed: the hand-written Compose above does what `ff start` would do. **Recommendation: the repo does not use `ff start`. It keeps its own Compose. `ff` is only a reference for generating config and is no longer a prerequisite.**

**Verdict: feasible.** FireFly attaches to our own externally-run QBFT Besu and writes to it on a zero-gas, London+Shanghai chain.

## Risk 3 — T-REX size and deploy: feasible for size, first deploy done

**What was run:** `@tokenysolutions/t-rex` 4.1.6 (npm) ships compiled artifacts (Solidity 0.8.17). Deployed bytecode sizes against the 24 576-byte limit (read from the artifacts):

| Contract | Deployed bytes | Init bytes |
|---|---|---|
| TREXFactory | 23 495 | 25 125 |
| Token | 14 245 | 14 287 |
| OwnerManager | 12 622 | 12 869 |
| AgentManager | 12 126 | 12 373 |
| ClaimIssuer | 11 687 | 12 428 |
| TREXImplementationAuthority | 8 995 | 9 462 |

All deployed sizes are under the limit; `TREXFactory` is the closest at about 1 KB of headroom. The init size of `TREXFactory` is above 24 576 but below the 49 152 init-code limit that applies from Shanghai. (read)

**First deploy:** the official `Token` artifact deployed through FireFly's deploy API as admin: HTTP 200, `Succeeded`, with a contract address. (run)

**Not yet done (Phase 2):** deploying the full suite in dependency order (ImplementationAuthority, registries, factory or direct proxies), because T-REX normally creates tokens through `TREXFactory`, and deploying that needs constructor arguments. The package also ships OnchainID contracts under `@onchain-id`.

## Risk 4 — EVM fork level: Shanghai works on our Besu

A contract compiled with `solc` 0.8.24 for `evmVersion: shanghai` (its bytecode begins with `5f`, which is PUSH0) deployed and ran correctly through FireFly on the London + Shanghai + `zeroBaseFee` genesis. The official T-REX artifacts are compiled with 0.8.17 and contain no PUSH0, so they run at any fork. (run)

**Still open:** the EVM version Paladin's own contracts need. That is answered in the Paladin spike (Risk 2). Until then D-08 stays as written (Shanghai or later with `zeroBaseFee`).

## Risk 7 — Idempotency and status names: answered

- FireFly accepts `idempotencyKey` in the invoke body. A second request with the same key returns **HTTP 409** with `FF10431: Idempotency key '...' already used for transaction '<original tx id>'`. The second write was not executed (the stored value stayed at the first request's value). (run)
- Operation/transaction status as returned in the response: `"status":"Succeeded"`. The failure value was not observed yet (revert test comes in Phase 2). (run)
- Implication for `core`: write calls should pass a stable `idempotencyKey`, and a 409 with FF10431 should be read as "already submitted", not as an error. The `core` rule "check state before every write" still applies to onboarding.

## Other findings

- `besu operator generate-blockchain-config` prints `Output directory already exists` when the output folder is a mounted volume path, but it still writes `genesis.json` and the keys. Treat the message as noise and check the files.
- `host.docker.internal` resolves from containers on Docker Desktop, so a Compose stack can reach a Besu published on the host. In the final repo the signer should point at `besu-rpc-anson` on the shared Compose network instead.
- `make` is missing on Windows. Needs a decision before Phase 1.

## Open items and decisions needed

1. **`make` on Windows:** install `make`, or replace the Make targets with a cross-platform script (for example a small Python entry point). Pending the user's decision.
2. **Docs updated from these results (2026-10-01):** `docs/plan.md` (D-03, Phase 0 step 1, open questions 1 and 7), `docs/deliverables.md` (prerequisites, DL-0.1 step 5) and `README.md` (prerequisites) now say: hand-written Compose, `ff` optional, `ff start` not used. **Still to update, with the user's approval:** `docs/prd.md` (US-001 criterion (a) and open question 1 mention `--remote-node-url`), `docs/use-cases.md` UC-01 ("attach with remote-node-url") and `docs/architecture.md` §9 (add the evmconnect and signer config facts, and drop "`evmconnect` is the default connector in `ff init`").
3. **Remaining spike work:** Risk 2 (Paladin), Risk 5 (Caliper), then sign-off.
