# spike/ — Phase 0 evidence (archive)

Throwaway experiments that answered the Phase 0 risks. Results and verdicts are in [../docs/spike-results.md](../docs/spike-results.md). Not part of the deliverable stack: the reusable parts (Compose, FireFly config, signer keystore layout) move to the real layout in Phase 1–2, and this folder stays as evidence.

> **Demo-only.** Every key, keystore and password here is a throwaway demo credential with no value (plan D-10). Never reuse them.

## Contents

| Path | What it is |
|---|---|
| `qbft/qbft-config.json` | Input for `besu operator generate-blockchain-config` (1 QBFT validator, London + Shanghai, `zeroBaseFee`, chainId 20260916) |
| `qbft/out/` | Generated `genesis.json` and validator key |
| `docker-compose.yml` | Single Besu node (`hyperledger/besu:26.8.1`) on host port 8545 |
| `firefly/docker-compose.yml` | FireFly gateway mode, 4 containers (Postgres, signer, evmconnect, core), attached to the Besu on the host |
| `firefly/config/` | `firefly_core.yml`, `evmconnect.yaml`, `ethsigner.yaml` |
| `firefly/gen-keys.mjs`, `signer-data/` | Generates and holds the admin / anson / beatrice keystores |
| `firefly/compile.mjs`, `contracts/SpikeStore.sol` | Compiles a tiny test contract (Shanghai and Berlin targets) |
| `firefly/deploy.mjs`, `deploy-artifact.mjs`, `invoke.mjs`, `idem.mjs` | Deploy, invoke, query and idempotency tests against FireFly's API |
| `paladin/docker-compose.yml`, `config/node1..3/` | Three Paladin nodes (`lfdecentralizedtrust/paladin:v1.0.0`) plus Postgres, attached to the Besu on the host. Configs hold demo BIP39 mnemonics and a demo DB password |
| `paladin/certs/` | Demo self-signed TLS certificates and keys, CN = node name (generated with `openssl` from the Paladin image) |
| `paladin/gen-nodes.mjs` | Writes the three node configs from `deployed.json` |
| `paladin/deploy-noto.mjs`, `artifacts/`, `deployed.json` | Deploys the registry and Noto contracts through node1 (artifacts from the Paladin v1.0.0 release) |
| `paladin/register-nodes.mjs` | Registers the three nodes and their gRPC transport details in the EVM registry |
| `paladin/noto-3node.mjs`, `coins-by-node.mjs` | Cross-node Noto flow, and a per-node view of which coin amounts each node can see (needs `NOTO_ABIS` pointing at the `abis.tar.gz` contents) |
| `paladin/noto-demo.mjs` | Earlier single-node Noto flow (kept for reference) |
| `caliper/` | Caliper 0.6.0 benchmark: chain layer (`network/ethereum.json`, `workload/set.js`) and FireFly layer (`connector/firefly-connector.js`, `network/firefly.json`). Install web3 by hand: `npm install --no-save web3@1.3.0` |

## Re-run it

```bash
# 1. Besu (genesis and key are already generated in qbft/out)
docker compose -f spike/docker-compose.yml up -d

# 2. FireFly
cd spike/firefly
npm install
docker compose up -d
curl -s http://localhost:5000/api/v1/status      # expect namespace "default", multiparty disabled

# 3. Deploy, then invoke and query using the address printed by deploy
node compile.mjs shanghai
node deploy.mjs shanghai
node invoke.mjs CONTRACT_ADDRESS anson 42
node idem.mjs CONTRACT_ADDRESS                   # second write returns HTTP 409 FF10431
```

Stop with `docker compose down` in each folder. `deploy-artifact.mjs ARTIFACT_JSON` deploys a compiled artifact, for example the official T-REX `Token`.
