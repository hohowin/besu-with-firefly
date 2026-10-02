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
