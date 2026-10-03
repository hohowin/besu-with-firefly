# Paladin contract artifacts

Compiled contracts and ABIs that Paladin v1.0.0 needs, vendored **unchanged** so that `python scripts/stack.py deploy` works offline from a fresh clone and the exact bytes are pinned.

| File | What it is |
|---|---|
| `core_v1alpha1_smartcontractdeployment_registry.yaml` | the EVM registry (constructor `[false]`) |
| `core_v1alpha1_smartcontractdeployment_noto.yaml` | the Noto implementation |
| `core_v1alpha1_smartcontractdeployment_noto_factory.yaml` | the Noto factory |
| `core_v1alpha1_smartcontractdeployment_noto_factory_proxy.yaml` | the proxy that the Noto domain is configured with |
| `INotoPrivate.json` | the ABI of Noto's private calls (`mint`, `transfer`, `balanceOf`, ...) |
| `SHA256SUMS` | SHA-256 of every file above; a unit test fails if one of them changes |

## Source

Paladin release `v1.0.0` (https://github.com/LF-Decentralized-Trust-labs/paladin/releases/tag/v1.0.0), licence **Apache-2.0**:

- the four `core_v1alpha1_smartcontractdeployment_*.yaml` files come from the release asset `artifacts.tar.gz` (SHA-256 `41e28f759e13af503e843b440149c2b1b04eb8e0aaa15d5d546c159ce3b1fc4f`). They are byte for byte the files used in the Phase 0 spike.
- `INotoPrivate.json` comes from the release asset `abis.tar.gz` (SHA-256 `3608c63573d8fd972236889e91acd26b8d08be4e77234557d6621b6a1c372c67`).

The YAML files are Kubernetes custom resources that the Paladin operator applies. This project does not use Kubernetes; it reads from each one only what a deployment needs: the ABI (`abiJSON`), the init code (`bytecode`), the key label that sends it (`from`), its constructor arguments (`paramsJSON`) and the contracts it needs first (`requiredContractDeployments`).

## Refreshing

Download both assets for the new release, replace the files, run `sha256sum <files> > SHA256SUMS` here, update the hashes above, and check the new bytecode against the image tag in `docker-compose.yml`.
