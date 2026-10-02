"""FireFly gateway-mode configuration text (pure, no I/O).

Derived from the working Phase 0 spike (`docs/spike-results.md`, Risk 1). Service names match
`docker-compose.yml`. No data exchange and no IPFS: gateway mode does not need them.
"""

import re

CHAIN_ID = 20260916
SIGNER_BACKEND_URL = "http://besu-rpc-anson:8545"

POSTGRES_HOST = "firefly-postgres"
POSTGRES_PASSWORD = "f1refly"  # demo only, internal to the Compose network
SIGNER_HOST = "firefly-signer"
EVMCONNECT_HOST = "firefly-evmconnect"
CORE_HOST = "firefly-core"

_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")

_CORE = """\
log:
  level: info
http:
  port: 5000
  address: 0.0.0.0
  publicURL: http://127.0.0.1:5000
admin:
  port: 5101
  address: 0.0.0.0
  enabled: true
spi:
  port: 5101
  address: 0.0.0.0
  enabled: true
event:
  dbevents:
    bufferSize: 10000
plugins:
  database:
  - name: database0
    type: postgres
    postgres:
      url: postgres://postgres:{postgres_password}@{postgres_host}:5432?sslmode=disable
      migrations:
        auto: true
  blockchain:
  - name: blockchain0
    type: ethereum
    ethereum:
      ethconnect:
        url: http://{evmconnect_host}:5008
        topic: "0"
namespaces:
  default: default
  predefined:
  - name: default
    description: Default predefined namespace
    defaultKey: {admin}
    plugins: [database0, blockchain0]
    multiparty:
      enabled: false
"""

_EVMCONNECT = """\
log:
  level: info
connector:
  url: http://{signer_host}:8545
persistence:
  leveldb:
    path: /evmconnect/data/leveldb
ffcore:
  url: http://{core_host}:5000
  namespaces:
    - default
confirmations:
  required: 0
policyengine.simple:
  fixedGasPrice: 0
  gasOracle:
    mode: fixed
api:
  port: 5008
  address: 0.0.0.0
  publicURL: http://127.0.0.1:5008
"""

_SIGNER = """\
server:
  port: 8545
  address: 0.0.0.0
backend:
  chainId: {chain_id}
  url: {backend_url}
fileWallet:
  path: /data/keystore
  filenames:
    primaryExt: .toml
  metadata:
    keyFileProperty: '{{{{ index .signing "key-file" }}}}'
    passwordFileProperty: '{{{{ index .signing "password-file" }}}}'
log:
  level: info
"""


def core_config(admin_address: str) -> str:
    """FireFly core config. `admin_address` becomes the namespace's default signing key."""
    if not _ADDRESS.match(admin_address):
        raise ValueError(f"not a valid admin address: {admin_address!r}")
    return _CORE.format(
        admin=admin_address.lower(),
        postgres_password=POSTGRES_PASSWORD,
        postgres_host=POSTGRES_HOST,
        evmconnect_host=EVMCONNECT_HOST,
    )


def evmconnect_config() -> str:
    """evmconnect config for a zero-gas QBFT chain: fixed gas price 0, no confirmations."""
    return _EVMCONNECT.format(signer_host=SIGNER_HOST, core_host=CORE_HOST)


def signer_config(chain_id: int = CHAIN_ID, backend_url: str = SIGNER_BACKEND_URL) -> str:
    """FireFly signer config. It talks to a Besu RPC node on the Compose network."""
    return _SIGNER.format(chain_id=chain_id, backend_url=backend_url)
