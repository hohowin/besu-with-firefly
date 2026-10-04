# Spike Results — Phase 0

> **Status: all 6 risks answered. Signed off by Howin Ho on 2026-10-02.** Started 2026-10-01. Deliverable DL-0.2 in `docs/deliverables.md`. Evidence labelled **run** was observed on a live container. **read** means taken from generated files or tool output. Throwaway spike files are in `spike/`.

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
| 4 | EVM fork level (D-08) | **Shanghai confirmed working** for FireFly, T-REX and Paladin Noto (run). Berlin not tried for Paladin | Revise D-08 |
| 7 | FireFly invoke idempotency and status names | **Answered** (run) | `core` checks state before every write |
| 2 | Paladin hand-written config on external Besu, Noto | **Feasible** with three nodes, Postgres, mTLS and the EVM registry (run) | Paladin on `kind` (not its own devnet Besu) |
| 5 | Caliper Besu connector and Node version | **Feasible with Caliper 0.6.0** (run). Caliper 0.7.1 dropped the Ethereum and Besu connectors. FireFly layer works through a custom connector (run) | Another load tool |

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

## Risk 2 — Paladin with hand-written config: feasible, three nodes with privacy proven

**How Paladin is built (read from the v1.0.0 image and the operator source):** the image is Ubuntu 24.04 running `java ... -jar /app/libs/paladin.jar`. The operator starts it with args `/app/config/pldconf.paladin.yaml engine --logtostderr=true --v=4`, so a plain Compose service can do the same. Native plugins ship in the image: `/app/domains/libnoto.so`, `/app/registries/libevm.so`, `/app/transports/libgrpc.so`, and DB migrations under `/app/db/migrations/{sqlite,postgres}`. Ports: 8548 (HTTP RPC), 8549 (WS RPC), 6100 (metrics).

**What was run (single node, SQLite, Compose in `spike/paladin/`):**
1. Hand-written `pldconf.paladin.yaml` with `nodeName`, `blockchain.http.url` and `blockchain.ws.url` (our Besu on the host), `db` (sqlite, `autoMigrate`, `migrationsDir`), `rpcServer`, and one `wallets` entry (static keystore holding a BIP39 mnemonic, `keyDerivation.type: bip32`, `seedKey.name: seed`). Result: the node starts, subscribes to Besu over WebSocket and indexes blocks. `transport_nodeName` returns `node1`. (run)
2. Key manager works: `keymgr_resolveKey` for `registry.operator` and `noto.operator` returns Ethereum addresses derived on BIP32 paths. Algorithm and verifier names are `ecdsa:secp256k1` and `eth_address`. (run)
3. **Contract deployment through Paladin's own RPC**, signed by its derived keys, in the operator's order: `registry` (constructor arg `[false]`) then `noto`, then `noto-factory`, then `noto-factory-proxy` (constructor args: the factory address and `0xc4d66de8000000000000000000000000` + the noto address, which calls `initialize(noto)`). All four succeeded on the zero-gas London/Shanghai chain. Method: `ptx_sendTransaction` with `{type: "public", from, abi, bytecode, data}`, then poll `ptx_getTransactionReceipt`. (run)
4. Added `domains.noto` (`plugin.type c-shared`, `library /app/domains/libnoto.so`, `config.factoryVersion 2`, `registryAddress` = the noto-factory-proxy address) and `registries.evm-registry` (`libevm.so`, `config.contractAddress` = the registry address). After a restart the Noto domain initialised (`domain initialization complete`, `domain_listDomains` returns `["noto"]`). (run)
5. **Noto end to end on one node:** deploy token (`type: private`, `domain: noto`, `from: notary@node1`, a constructor ABI with `notary` and `notaryMode: "basic"`; without the constructor ABI the call fails with `PD200007: Parameter 'notary' is required`), `mint` 100 to `anson@node1`, `transfer` 40 to `beatrice@node1`. Balances read back through `ptx_call balanceOf`: anson 60, beatrice 40. (run)
6. **Public chain check:** the Noto token emitted 4 logs. Scanning all 39 32-byte words in their data and topics found none equal to 100, 40 or 60. Mint and transfer logs carry a transaction id, state hashes, a proof and opaque data. (run)

**Config facts that matter:**
- The image runs as uid 1001. `/app/jna` must be writable **and executable** (a Docker `tmpfs` is `noexec` by default and the node dies with `failed to map segment from shared object`). Use `tmpfs: /app/jna:exec,mode=1777`.
- `/db` for SQLite must be writable by uid 1001. A `tmpfs` loses state on container recreate; use a volume in the real stack.
- Registry and domain contracts must be deployed **before** the domain config is written, so bootstrapping is two-phase: start with no domains, deploy, write the addresses into config, restart.
- Names used in the key paths come from the operator (`registry.operator`, `noto.operator`, `noto_factory.operator`, `noto_factory_proxy.operator`). They are only labels for derived keys, so any names work.
- Paladin's artifact YAML files (ABI plus bytecode) come from the release asset `artifacts.tar.gz`. The private Noto ABIs (`INotoPrivate.json`, `mint`, `transfer`, `balanceOf`) come from `abis.tar.gz`. Both are Apache-2.0 release assets, copied into `spike/paladin/artifacts/` where needed.

**Three-node setup (run), in `spike/paladin/`:** node1 = notary and registry admin, node2 = Anson, node3 = Beatrice, plus one Postgres container with a database per node.

1. **Transport.** Each node has `transports.grpc` with `plugin.library /app/transports/libgrpc.so` and `config` `{port 9000, address 0.0.0.0, externalHostname paladin-nodeN, tls {enabled, clientAuth, certFile, keyFile, caFile}}`. TLS is required. The transport identifies a peer by the **certificate subject CN = the node name**, requires **exactly one leaf certificate**, and verifies it against the issuer certificate that the peer published in the registry. A self-signed certificate per node works (`openssl req -x509`, CN = `node1`, with `basicConstraints CA:TRUE`, `keyUsage digitalSignature,keyCertSign`, `extendedKeyUsage serverAuth,clientAuth`, `ca.crt` = the same certificate). Server and client `TLS handshake completed` appeared between node1/node2 and node2/node3. The Paladin image has `openssl` for generating them.
2. **Registry registration** (mirrors the operator's `PaladinRegistration`): node1's `registry.operator` key calls `registerIdentity(parentIdentityHash = 0x00..00, name = nodeN, owner = nodeN's registry.nodeN key address)`. Then each node calls `setIdentityProperty(identityHash, "transport.grpc", <transport_localTransportDetails("grpc")>)` with its own `registry.nodeN` key. The identity hash comes from `reg_queryEntries`. Transport details are `{"endpoint":"dns:///paladin-nodeN:9000","issuers":"<PEM>"}`.
3. **Cross-node Noto.** Deploy the token on node1 with `notary: notary@node1`, `notaryMode: basic`. Mint 100 to `anson@node2` (submitted on node1). Transfer 40 from `anson@node2` to `beatrice@node3` (submitted on node2). Balances: Anson 60 on node2, Beatrice 40 on node3. (run)
4. **Privacy, measured by the coin amounts each node can see** after the transfer: node1 (notary) 40, 60, 100. node2 (Anson) 40, 60, 100. **node3 (Beatrice) 40 only.** Before the transfer, right after the mint, node3 saw no states at all. On-chain, the token's 4 logs contain no plain 100, 40 or 60. So D-05 holds: the receiving party sees only its own coin, a non-party sees nothing, and the notary sees everything (which is how Noto's notary model works). (run)

**More config facts:**
- **SQLite stalls under multi-node load; use Postgres.** With SQLite, node1's block indexer stopped at block 17106 right after the coordinator dispatched a public transaction, `ptx_queryPublicTransactions` timed out after 120 s with `context deadline exceeded`, and the transfer never completed. The same flow completed first time on Postgres. This matches the Paladin operator, whose default is a sidecar Postgres. Config: `db.type: postgres`, `db.postgres.dsn: postgres://USER:PASSWORD@postgres:5432/NODE?sslmode=disable`, `autoMigrate: true`, `migrationsDir: /app/db/migrations/postgres`. One server with one database per node is enough.
- **Key derivation is not reproducible from the mnemonic alone.** Paladin assigns the BIP32 path index of each identifier segment (`registry`, `noto`, ...) in the order it first resolves them, and stores that mapping in its DB. After a DB wipe, `registry.operator` resolved to a different address, which made `registerIdentity` revert with `Forbidden` because the registry's root owner was the old address. Keep the DB (a volume) between restarts, and in the bootstrap script deploy the registry and factory after the DB is created, not before.
- A fresh node indexes the whole chain from block 0 (about 1 500 blocks per 12 s on Postgres), so the first start of a long-lived chain takes a while. The chain here was about 17 400 blocks.
- `ptx_sendTransaction` for a deploy needs the constructor ABI for private domains. Names such as `registry.nodeN` are free labels.
- Bootstrap order that worked: start nodes (domain config can point at any valid factory address), deploy registry and Noto contracts through node1, write the new addresses into every node's config, restart, register nodes in the registry, then use Noto.

**Verdict: feasible.** A hand-written Compose with three Paladin nodes, Postgres and self-signed certificates attaches to our own Besu and runs Noto with real party privacy. The operator-only parts (CRDs, cert-manager, Kubernetes) are not needed. Still untested: Zeto and Pente (out of MVP), and the EVM version Paladin needs below Shanghai.

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

**Paladin:** its registry and Noto contracts deployed and ran on this Shanghai genesis (see Risk 2). Whether they would also run on Berlin was not tried, so D-08 stays as written (Shanghai or later with `zeroBaseFee`).

## Risk 7 — Idempotency and status names: answered

- FireFly accepts `idempotencyKey` in the invoke body. A second request with the same key returns **HTTP 409** with `FF10431: Idempotency key '...' already used for transaction '<original tx id>'`. The second write was not executed (the stored value stayed at the first request's value). (run)
- Operation/transaction status as returned in the response: `"status":"Succeeded"`. The failure value was not observed yet (revert test comes in Phase 2). (run)
- Implication for `core`: write calls should pass a stable `idempotencyKey`, and a 409 with FF10431 should be read as "already submitted", not as an error. The `core` rule "check state before every write" still applies to onboarding.

## Risk 5 — Caliper: feasible with 0.6.0, not 0.7.1

**What was run (`spike/caliper/`, Node v24.11.1, npm 11.6.2, Windows):**
1. **Caliper 0.7.1** (`@hyperledger/caliper-cli`, latest) needs Node >= 22 and npm >= 11.5.1, which this machine meets, **but its CLI no longer knows the `ethereum` or `besu` SUT** (`caliper bind` fails with `Unknown SUT type`). The last published Ethereum connector is `@hyperledger/caliper-ethereum` **0.6.0**. (run)
2. **Caliper 0.6.0** (`caliper-cli`, `caliper-core`, `caliper-ethereum` all 0.6.0, engines Node >= 18.19) accepts `besu` and `ethereum`, and runs on Node 24. (run)
3. **`caliper bind` is broken on Windows** with `spawn EINVAL` (Node's security change for spawning `.cmd` files). `bind` only runs `npm install web3@1.3.0`, so install that by hand: `npm install --no-save web3@1.3.0`, and do not pass `--caliper-bind-sut` to `launch`. (run)
4. **Chain-layer round works.** `SpikeStore.set()` sent directly to Besu through the Ethereum connector. Command: `npx caliper launch manager --caliper-workspace . --caliper-benchconfig benchmarks/spike.yaml --caliper-networkconfig network/ethereum.json --caliper-flow-skip-start --caliper-flow-skip-end`. (run)
5. **FireFly-layer round works through a custom connector.** Caliper has no FireFly connector, and a plain workload cannot record results by itself. A ~40-line connector (`connector/firefly-connector.js`, extends `ConnectorBase`, `_sendSingleRequest` returns a `TxStatus`) calls FireFly's `contracts/invoke?confirm=true`. It is selected with `"caliper": {"blockchain": "./connector/firefly-connector.js"}` in a separate network config. The same workload module is reused. (run)

**Connector facts that matter:**
- The Ethereum connector **requires a `ws://` URL**; an `http(s)` URL is rejected. Besu must have `--rpc-ws-enabled`.
- Contract deployment happens in Caliper's **install** step, so do not use `--caliper-flow-skip-install` for the chain-layer round.
- The deploy gas comes from a `gas` property **inside the contract JSON file** (`{name, abi, bytecode, gas}`), not from the network config. The per-method gas (`gas: {set: 100000}`) goes in the network config.
- Transaction confirmation is `transactionConfirmationBlocks: 1`; the account needs no balance on this zero-gas chain.
- Caliper 0.6.0 pulls deprecated dependencies (web3 1.3.0, old `glob`, `core-js` 2). That is acceptable for a local demo, but pin the exact versions.

**Indicative numbers only, not a benchmark** (one local worker, 60 transactions, 20 TPS offered, a single-validator Besu with 2 s blocks, one signing key, one run):

| Layer | Succeeded | Avg latency | Max latency | Throughput |
|---|---|---|---|---|
| Chain (direct JSON-RPC) | 60 / 60 | 0.96 s | 2.05 s | 12.4 TPS |
| FireFly (`invoke?confirm=true`) | 60 / 60 | 2.68 s | 4.50 s | 9.8 TPS |

These prove the method works and that FireFly adds measurable latency. They are not a result: the sample is tiny, the network is one validator, and numbers will change with 4 validators, more workers and more keys. Phase 5 produces the real numbers.

**Verdict: feasible.** Use Caliper 0.6.0 with a manual `web3@1.3.0` install. The FireFly layer needs the small custom connector (D-14 should say "custom connector", not "custom HTTP workload").

## Versions to pin

| Component | Version used in the spike |
|---|---|
| Besu | `hyperledger/besu:26.8.1` |
| FireFly core | `ghcr.io/hyperledger-firefly/firefly@sha256:d321bcd8c567430498b7e330e075f97b9aa1888e166c76a95b4b2df161b105b8` (the `latest` tag when generated; a `v1.5.0` release exists) |
| evmconnect | v1.5.1, `@sha256:ca6e3860c784477cd800bcbf00506310a31992468bd5b2c1f4bd2a1317d2b03b` |
| FireFly signer | v1.2.1, `@sha256:412236dfab0416ae3d60f4fecb311b067664a9dd4f16073856eb79a25f4c532f` |
| FireFly Postgres | `postgres:16-alpine` |
| Paladin | `lfdecentralizedtrust/paladin:v1.0.0` (v1.0.1-rc.1 exists, not used) |
| Paladin Postgres | `postgres:17-alpine` |
| T-REX contracts | `@tokenysolutions/t-rex` 4.1.6 (artifacts compiled with Solidity 0.8.17) |
| Caliper | `@hyperledger/caliper-cli`, `caliper-core`, `caliper-ethereum` 0.6.0, plus `web3@1.3.0` |
| FireFly CLI (optional reference) | `ff` v1.5.0, built with `go install github.com/hyperledger-firefly/cli/ff@v1.5.0` |
| Node.js / npm | v24.11.1 / 11.6.2 |
| Python | 3.13.3 |
| Docker engine | 29.5.2 (Docker Desktop) |
| ethers (demo keys) | 6.13.4 |
| solc (test contract) | 0.8.24 |

## Other findings

- `besu operator generate-blockchain-config` prints `Output directory already exists` when the output folder is a mounted volume path, but it still writes `genesis.json` and the keys. Treat the message as noise and check the files.
- `host.docker.internal` resolves from containers on Docker Desktop, so a Compose stack can reach a Besu published on the host. In the final repo the signer should point at `besu-rpc-anson` on the shared Compose network instead.
- `make` is missing on Windows. Needs a decision before Phase 1.

## Open items and decisions needed

All resolved on 2026-10-02 when the developer signed off Phase 0 and asked for the follow-up changes:

1. **Task runner:** `make` is not installed on Windows, so the project uses a Python script, `python scripts/stack.py up|deploy|reset` (plan D-16). All docs were updated.
2. **Docs updated from these results:** `README.md`, `docs/prd.md`, `docs/plan.md` (D-03, D-05, D-08, D-09, D-14, D-15, D-16, Phase 0, Phase 3 and 5 steps, open questions), `docs/architecture.md` (topology, Paladin and FireFly rows, TBD list), `docs/use-cases.md` (UC-01, UC-08, UC-10) and `docs/deliverables.md` (Phase 0 done, DL-3.x, Caliper notes).
3. **Carried into later phases:** the full T-REX suite deployment in dependency order (Phase 2), the cross-platform stack script (Phase 1), and the real Caliper numbers (Phase 5).

## Phase 2 findings

Added during Phase 2 (Task 5, 2026-10-02). Evidence labelled **read** comes from the pinned packages' sources and artifacts, **run** from the live stack.

### T-REX suite: what to deploy, and in what order (read)

Pinned in `contracts/package.json`: `@tokenysolutions/t-rex` **4.1.6** and `@onchain-id/solidity` **2.1.0**, installed with `npm ci` (nothing is compiled; `contracts/node_modules/` is gitignored; both packages are licensed GPL-3.0 and ISC respectively, so no contract code is copied into this repo).

- **The T-REX package alone is not enough.** It bundles compiled OnchainID `Identity`, `ClaimIssuer` and `ImplementationAuthority`, but **not `IdFactory`** (only its interface), and `TREXFactory` needs an IdFactory. So all OnchainID contracts are taken from `@onchain-id/solidity`.
- **Version choice.** The OnchainID ABIs of `Identity`, `ClaimIssuer` and `ImplementationAuthority` are identical in 2.0.0, 2.0.1 and 2.1.0 and the same as the copies bundled in t-rex 4.1.6; 2.2.x changes the `Identity` ABI. So 2.1.0 is pinned. The bundled copies are compiled with other settings (bundled `Identity` is 9,253 bytes, the package's own is 16,186), so their bytecode differs; the project does not mix them.
- **Order** (the plan in `src/core/trex/plan.py`, checked against the real ABIs by a test):
  1. OnchainID `Identity` implementation `(admin, isLibrary=true)`, then `ImplementationAuthority(identity)`, then `IdFactory(authority)`.
  2. The six T-REX implementations, no constructor arguments: `Token`, `ClaimTopicsRegistry`, `IdentityRegistry`, `IdentityRegistryStorage`, `TrustedIssuersRegistry`, `ModularCompliance`.
  3. `TREXImplementationAuthority(referenceStatus=true, trexFactory=0x0, iaFactory=0x0)`, then **`addAndUseTREXVersion({4,1,6}, {the six implementations})` before the factory exists**. The factory's constructor reverts with `invalid Implementation Authority` unless the authority already holds all six implementations. (Reading the source first gave the wrong order; the chain corrected it, see below.)
  4. `TREXFactory(trexAuthority, idFactory)`.
  5. `ClaimIssuer(admin)`, so Admin is its management key and can sign KYC claims.
  6. Registering the factory, as Admin: `trexAuthority.setTREXFactory(factory)` (requires the factory to report that authority) and `idFactory.addTokenFactory(factory)`.
- **Then** `TREXFactory.deployTREXSuite(salt, tokenDetails, claimDetails)` creates the token and its five proxies (token, IdentityRegistry, IdentityRegistryStorage, ClaimTopicsRegistry, TrustedIssuersRegistry, ModularCompliance) by CREATE2 and calls `IdFactory.createTokenIdentity`, which is why the factory must be a token factory of the IdFactory. It is `onlyOwner` (Admin deployed it) and takes at most 5 agents, 5 claim topics, 5 trusted issuers. `getToken(salt)` returns the token. That is Task 7.

### Contract sizes (read)

All deployed sizes are under the 24,576-byte limit and all init sizes under the 49,152-byte Shanghai limit. `TREXFactory` is the closest, with 1,081 bytes of headroom (it embeds the proxies' creation code). Its init size (25,125) is over 24,576 but allowed from Shanghai (EIP-3860), which this chain has from block 0.

| Plan name | Contract | Deployed bytes | Init bytes | Headroom to 24,576 |
|---|---|---|---|---|
| identity-implementation | Identity | 16,186 | 17,589 | 8,390 |
| identity-implementation-authority | ImplementationAuthority | 1,643 | 2,488 | 22,933 |
| id-factory | IdFactory | 17,717 | 18,510 | 6,859 |
| token-implementation | Token | 14,245 | 14,287 | 10,331 |
| claim-topics-registry-implementation | ClaimTopicsRegistry | 1,987 | 2,019 | 22,589 |
| identity-registry-implementation | IdentityRegistry | 6,910 | 6,942 | 17,666 |
| identity-registry-storage-implementation | IdentityRegistryStorage | 4,534 | 4,566 | 20,042 |
| trusted-issuers-registry-implementation | TrustedIssuersRegistry | 5,201 | 5,233 | 19,375 |
| modular-compliance-implementation | ModularCompliance | 5,619 | 5,651 | 18,957 |
| trex-implementation-authority | TREXImplementationAuthority | 8,995 | 9,462 | 15,581 |
| trex-factory | TREXFactory | 23,495 | 25,125 | 1,081 |
| claim-issuer | ClaimIssuer | 19,987 | 21,311 | 4,589 |

**Verdict: the full suite deploys through FireFly on our Besu, and D-04 and risk R3 hold** (see "Creating COIN" below).

### Creating COIN (run, Task 7)

`TREXFactory.deployTREXSuite("coin", tokenDetails, claimDetails)` is one FireFly invoke as Admin. It succeeded on the first try on our Besu (about 6 seconds, one transaction), creating the token and its identity registry, identity registry storage, claim topics registry, trusted issuers registry and modular compliance as proxies, all code-checked on chain. The token's details are `Coin`, `COIN`, 18 decimals, owner Admin, Admin as agent of both the registry and the token, one claim topic (`1`, KYC) and the `ClaimIssuer` as trusted issuer for it; no compliance modules. The addresses are read back, not assumed: `factory.getToken("coin")`, then `token.identityRegistry()` and `token.compliance()`, then `identityRegistry.identityStorage()`, `.topicsRegistry()` and `.issuersRegistry()` (the registry getter is `identityStorage`, not `identityRegistryStorage`; a test checks every name read against the real ABIs). Gas was not an issue: the genesis gas limit is `0x1fffffffffffff` and evmconnect estimates it.

### QBFT pauses when only a quorum is alive (run, Task 13)

> **Superseded 2026-10-03 (plan D-17):** the network now has one validator, so this situation cannot arise. The finding is kept because it is why the network was reduced.

With 4 validators and one stopped, the other 3 are exactly the quorum (3), so all three must be in the same round before a block is made. On a busy machine one of them sometimes lags, the three end up in different rounds, and QBFT's round timer doubles each time (`requesttimeoutseconds` 4, then 8, 16, 32, 64 s). The validator logs showed rounds 2, 3 and 4 at once and `Moved to round 4 which will expire in 64 seconds`, and blocks stopped for minutes. In 6 repeated runs of the fault-injection tests, 2 failed (one that way, one because `besu-rpc-anson` did not report 4 peers again within 90 s of a validator restart: measured, an RPC node dials a restarted validator again only on a 60 s cycle (61 s after the restart), so the test now allows 150 s). With all 4 validators alive there is a spare, so the effect is rare. The plan keeps `requesttimeoutseconds` 4 and the 30-second assertion; the developer accepted occasional failures of those tests (2026-10-02). Lowering the timeout or relaxing the assertions are the options that were not taken. Instead the two tests that stop validators carry the marker `fault_injection` and are reported separately from the integration gate, and the cleanup that waits for blocks to resume after a restore is patient (300 s). In later full runs the rate was about one failure per run; in the last three runs of the fault group alone they passed 2 of 2 each time.

### Compliance rejection (run, Task 12)

A transfer from Anson to the unverified Admin is refused **by the token contract**, not by this project's code:

- Straight to Besu, `eth_call` of `transfer(admin, 1)` from Anson reverts with `Error("Transfer not possible")` (selector `0x08c379a0`), while the same call to the verified Beatrice returns `true`.
- Through FireFly's generated API, with or without `?confirm=true`, the answer is **HTTP 500** with `{"error": "FF10111: Error from ethereum connector: FF23021: EVM reverted: Error(\"Transfer not possible\")"}`. The revert is found while estimating gas, so **nothing is mined**: balances and total supply are unchanged.
- FireFly still records the attempt: an operation of type `blockchain_invoke` with **status `Failed`** and the same text in its `error` field. This closes the Risk 7 gap: the failure status is `Failed`.
- The revert reason is T-REX's generic `Transfer not possible`; it does not say which check failed (here: the recipient is not verified, which the Anson to Beatrice contrast shows). The client turns this into a `Reverted` error with `reason`, which Phase 4's CLI can show as a compliance error.

### Identities and KYC claims (run, Tasks 9 and 10)

- `IdFactory.createIdentity(wallet, salt)` (owner only, so Admin) creates the wallet's OnchainID proxy; the wallet becomes its management key. `IdFactory.getIdentity(wallet)` returns the zero address when there is none. `IdentityRegistry.registerIdentity(wallet, identity, country)` works for Admin because the factory made Admin a registry agent; `contains(wallet)` is the "is registered" read.
- **A KYC claim** is signed by a key of the `ClaimIssuer` over `keccak256(abi.encode(identity, topic, data))` with the Ethereum signed-message prefix (65-byte signature, `v` 27 or 28). The issuer is managed by Admin, and a management key also passes the claim-key check, so Admin signs. The claim is **added by the identity's owner** (`addClaim` needs a claim or management key on the identity: the investor's own FireFly key), which makes `IdentityRegistry.isVerified(wallet)` true because the claim topic and issuer are trusted by the token's registries.
- The chain itself confirms the signature: `ClaimIssuer.isClaimValid(identity, topic, signature, data)` is true for the stored claim and for Admin's signature, and false for one signed by another wallet.
- **A write can time out inside FireFly and still succeed.** Once, a deploy right after `up` returned `HTTP 500 ... context deadline exceeded` (core gave up after 30 s waiting for evmconnect, which waited for the signer); FireFly then retried the operation itself and it `Succeeded` about 45 seconds after submission. The runner therefore retries a transient failure under the same key, then waits for the accepted transaction and takes its address from the operation output. This was seen once in about eight cold starts and did not recur in three later ones.

### Contract interfaces and APIs (run, Task 8)

- `POST /contracts/interfaces/generate` accepts `name` and `version` next to `input.abi`; posting its result to `POST /contracts/interfaces?confirm=true` registers it (HTTP 200, with an `id`). A second registration of the same name and version is **HTTP 409 `FF10407`** (conflicts with the existing one), not a no-op, so the client lists first (`GET /contracts/interfaces?name=&version=`). The same holds for `POST /apis` (`GET /apis?name=`).
- `POST /apis` with `{name, interface: {id}, location: {address}}` creates the API; `POST /apis/{name}/query/{method}` returns `{"output": <value>}` and `POST /apis/{name}/invoke/{method}?confirm=true` takes `{input, key, idempotencyKey}`. Arguments are by parameter name (`balanceOf` takes `_userAddress`).
- An interface's methods are only returned by `GET /contracts/interfaces/{id}?fetchchildren=true` (the list and `?fields=true` do not show them).
- **A new T-REX token is paused** (`paused()` returns `true`). `unpause()` as Admin (a token agent) through the `coin` API succeeds; `deploy` does this when the token is still paused.

### Deploying through FireFly (run, Task 6)

From a reset stack, `python scripts/stack.py deploy` deploys the 12 contracts and makes the 3 wiring calls in about 33 seconds, with no manual step. Addresses are the same on every fresh chain (same deployer, same nonces).

- **A reverted deploy** with `?confirm=true` comes back as **HTTP 500** with `{"error": "FF10111: Error from ethereum connector: FF23021: EVM reverted: Error(\"invalid Implementation Authority\")"}`, not as HTTP 200 with a failed status. The revert reason is in the text.
- **The operation's final status for a failure is `Failed`**, with the same text in its `error` field (`GET /transactions/{id}/operations`). This fills the Risk 7 gap about the failure value.
- **A failed transaction keeps its idempotency key.** Sending the same key again returns 409 `FF10431` even though nothing was mined. The deploy runner therefore checks the original transaction's operations: if all failed it retries under `<key>-after-<first 8 characters of the transaction id>`, if it succeeded it counts as done (a call) or asks for `reset` (a deploy whose address was not recorded).
- **`POST /contracts/interfaces/generate`** with `{"input": {"abi": [...]}}` returns a contract interface whose methods work as the `method` of an invoke, including struct parameters (the `addAndUseTREXVersion` call uses it). Nothing is registered by calling it.
- Calls are passed to FireFly by parameter name, so the plan's positional arguments are paired with the ABI's parameter names.

## Phase 3 findings

What building Phase 3 (Paladin and Noto in the real stack) added to the spike. Dated 2026-10-04.

### Bootstrap and registry (run)

- **Two-phase bootstrap.** The nodes first start from a base config without domains. `deploy` then sends the registry, Noto, Noto factory and factory proxy contracts through node1, writes `domains.noto` (registry address = the factory proxy, `factoryVersion` 2) and `registries.evm-registry` into every node's config, and restarts the nodes. After that `domain_listDomains` returns `["noto"]` on all three. Paladin's `ptx_sendTransaction` accepts the deploy with the artifact ABI and bytecode and signs with its own derived key.
- **Registering a node takes two transactions from two keys.** `registerIdentity` is sent by node1's `registry.operator` (the registry's root owner) with the node's own `registry.<node>` address as owner; the node then publishes `transport.grpc` with `setIdentityProperty` using its own key. `reg_queryEntriesWithProps` shows the entry and its properties.
- **node1's index lags the chain.** A registration is mined before `reg_queryEntriesWithProps` shows it. Asking straight after the registration sometimes missed the entry (`KeyError: 'node3'` in the first cold `deploy`). `deploy` now polls (up to 60 s) before setting the transports. After that fix three cold `reset`, `up`, `deploy` cycles all exited 0.
- **Timings** on this machine: cold `up` 49 to 111 s, `deploy` with Paladin 113 to 129 s.

### Noto across three nodes (run)

- Deploying a token needs a constructor ABI with `notary` and `notaryMode`; the notary is `notary@node1` and the mode is `basic`. The receipt of the private deploy has `contractAddress`.
- `mint` is sent by the notary on node1, `transfer` by the coin's owner on the owner's own node. `balanceOf` answers `{totalStates, totalBalance, overflow}` with numbers as strings; it must be asked of the owner's node.
- The first call between nodes opens the gRPC connections: node1's log then shows `Client TLS handshake completed` and `Server TLS handshake completed` with node2 and node3.
- An oversize transfer fails at assembly: `PD012616: Domain reverted transaction on assemble: PD200005: Insufficient funds (available=...)`. Once, right after a mint, the message said `available=200` for a 100 balance; the transfer was still refused and `balanceOf` stayed 100, so it is the message only.
- **What each node lists** (`pstate_queryContractStates`, state `data.amount`, spent coins included): after the mint node1 and node2 list 100 and node3 lists nothing; after a transfer of 40 node1 and node2 list 40, 60 and 100 and node3 lists 40 only. The public chain's logs for the token have no 32-byte word equal to 100, 60 or 40 and no wallet address of Anson or Beatrice.

### Reset and restart (run)

- A plain `docker restart` of the three Paladin containers keeps `registry.operator` and `registry.<node>` addresses, the registry entries and balances, because the Postgres database is a volume (the spike's key-derivation hazard).
- `reset` removes the Paladin Postgres volume, `paladin-runtime/` and `deployed-addresses.json`; after the next `up` every node reports no domain until `deploy` runs again.

### Result

`pytest -m integration` (103 tests) passed three times in a row from `reset`, `up` and `deploy` (772 s, 750 s, 707 s). Unit tests (439), `ruff check` and `mypy` are clean.

## Phase 4 findings

**Events for `besu-ff tx` (probed 2026-10-04 on the live stack, FireFly v1.5.0).** For a succeeded `blockchain_invoke` operation with no contract listener registered:

| Endpoint | Result |
|---|---|
| `GET /events?tx={transactionId}` | two FireFly events: `transaction_submitted` and `blockchain_invoke_op_succeeded` (used by the CLI) |
| `GET /transactions/{id}/blockchainevents` and `GET /blockchainevents?tx={id}` | `[]`: blockchain events exist only for a registered contract listener |
| `GET /transactions/{id}/status` | the operation step only, with the transaction hash and block (no events) |
| `GET /transactions/{id}/events` | `FF10109: Not found` (no such route) |

So `tx` shows FireFly's own transaction events and registers no listener (task list Open Question 3). The real response is stored in `tests/unit/adapters/recorded/events_by_tx.json`.

## Phase 5 findings

**Task 1 probes (2026-10-04, Caliper 0.6.0, Node v24.11.1, npm 11.6.2, the real stack).**

- **A. An already deployed contract can be used with `--caliper-flow-skip-install`, but only if the network config carries the contract's `abi` inline next to its `address`.** With `path` and `address` alone the worker fails with `You must provide the json interface of the contract when instantiating a contract object`, because the connector sets `abi` only inside `installSmartContract` (the deploy step). With `abi` and `address` inline, `COIN.name()` ran 10 of 10 (read-only, 5 TPS). `perf/lib/prepare.js` writes that config from `deployed-addresses.json` and the pinned T-REX `Token.json`, so the token address is not committed.
- **B. A worker's own sender comes from `fromAddressSeed`.** The connector derives `m/44'/60'/<workerIndex>'/0/0` from `EthereumHDKey.fromMasterSeed(seed)` (the seed string is hashed as UTF-8 bytes) and keeps a nonce per worker, so N senders means N workers. For the seed `besu-with-firefly perf demo seed` workers 0, 1 and 2 are `0x625c876b12ee5de00f848e4ff2644280cf4420b8`, `0x6c8b51832c5ff5d14d70c215e825ea38d3490478` and `0xe877993fcb99db7728cfd2bf51d04021e0bbea29` (printed by `perf/lib/derive.js`, which makes the same call as the connector). A write from a derived key was not run in this task: it needs a verified wallet (Task 3). The zero-gas path itself is the one the spike already exercised (`gasPrice` 0, explicit nonce, 60 of 60 sent).

**Task 2 probe (2026-10-04): FireFly's signer does not pick up new keystore files, and names them by address.**

- Two keystore files written into `network-config/firefly/signer-data/keystore` while the signer ran were visible inside the container, but `eth_accounts` did not list the new address after 20 s, and the signer has no refresh method (`wallet_refresh` and the like answer `Method not found`). `docker restart firefly-signer` loads them (back to `healthy` in about 20 s, FireFly keeps working).
- The signer takes the address from the **file name**: a pair named `perf-001` and `perf-001.toml` is ignored with `Ignoring '/data/keystore/perf-001': invalid address ''`. So the benchmark keystores are named by address like the committed ones, and cannot be gitignored by a prefix; `.gitignore` ignores everything new in that folder instead (files already tracked stay tracked).
- Python derivation (`src/core/perf/wallets.py`, BIP32 over `eth_keys`) gives the same addresses and keys as Caliper's connector for workers 0, 1 and 2 (the vectors above).

**Task 4 finding (2026-10-04): Caliper 0.6.0 treats `txNumber` and `tps` as totals for the round and splits them across the workers.** With 10 workers, `txNumber: 60` and `tps: 2` gave 60 transactions in all at about 2 TPS in all (not 600 at 20), so the benchmark file carries the totals. The first chain-layer round on the real token (10 wallets, 600 transfers, 20 TPS offered, one validator with 2 s blocks): 600 of 600 succeeded, 19 TPS, average latency 1.86 s, maximum 2.98 s. This is one run; the numbers that count come from Task 6.
