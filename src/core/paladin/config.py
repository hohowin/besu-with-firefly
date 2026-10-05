"""Paladin node configuration text (pure, no I/O).

Derived from the working Phase 0 spike (`docs/spike-results.md`, Risk 2). This is the **base**
config: the node can start with it, but it has no `domains` and no `registries` block because the
registry and Noto contracts do not exist yet. `deploy` deploys them through node1 and writes the
final config (base plus those two blocks) before restarting the nodes.
"""

from eth_account.hdaccount.mnemonic import Mnemonic
from eth_account.types import Language

NODES = ("node1", "node2", "node3")  # node1 notary and registry admin, node2 Anson, node3 Beatrice

RPC_HTTP_PORT = 8548
RPC_WS_PORT = 8549
GRPC_PORT = 9000

# The Paladin image ships a web UI in /app/ui. It is served only when `staticServers` enables it,
# on the HTTP RPC port: http://localhost:8548/ui/ on node1 (8648 and 8748 on the others).
# `baseRedirect` sends `/ui` to `/ui/`, because the page loads its assets by relative path and is
# blank without the trailing slash.
UI_PATH = "/ui"
UI_STATIC_PATH = "/app/ui"

POSTGRES_HOST = "paladin-postgres"
POSTGRES_PASSWORD = "paladin-demo-pw"  # demo only, internal to the Compose network
BESU_HTTP_URL = "http://besu-rpc-anson:8545"
BESU_WS_URL = "ws://besu-rpc-anson:8546"

_BASE = """\
nodeName: {node}
log:
  level: info
blockchain:
  http:
    url: {http_url}
  ws:
    url: {ws_url}
db:
  type: postgres
  postgres:
    dsn: "postgres://postgres:{postgres_password}@{postgres_host}:5432/{node}?sslmode=disable"
    autoMigrate: true
    migrationsDir: /app/db/migrations/postgres
rpcServer:
  http:
    address: 0.0.0.0
    port: {rpc_http}
    staticServers:
      - enabled: true
        staticPath: {ui_static}
        urlPath: {ui_path}
        baseRedirect: {ui_path}/
  ws:
    address: 0.0.0.0
    port: {rpc_ws}
wallets:
- name: wallet1
  keySelector: ".*"
  signer:
    keyDerivation:
      type: bip32
      seedKey:
        name: seed
    keyStore:
      type: static
      static:
        keys:
          seed:
            encoding: none
            inline: "{mnemonic}"
transports:
  grpc:
    plugin:
      type: c-shared
      library: /app/transports/libgrpc.so
    config:
      port: {grpc}
      address: 0.0.0.0
      externalHostname: paladin-{node}
      tls:
        enabled: true
        clientAuth: true
        certFile: /certs/tls.crt
        keyFile: /certs/tls.key
        caFile: /certs/ca.crt
"""


def validate_mnemonic(phrase: str) -> None:
    """Raise ValueError unless `phrase` is a valid 12-word BIP39 mnemonic."""
    if len(phrase.split()) != 12:
        raise ValueError(f"a mnemonic must have 12 words, got {len(phrase.split())}")
    if not Mnemonic(Language.ENGLISH).is_mnemonic_valid(phrase):
        raise ValueError("not a valid BIP39 mnemonic")


def base_config(node: str, mnemonic: str) -> str:
    """The config a Paladin node starts with, before the Noto domain and registry exist."""
    if node not in NODES:
        raise ValueError(f"unknown node {node!r}, expected one of {list(NODES)}")
    validate_mnemonic(mnemonic)
    return _BASE.format(
        node=node,
        http_url=BESU_HTTP_URL,
        ws_url=BESU_WS_URL,
        postgres_password=POSTGRES_PASSWORD,
        postgres_host=POSTGRES_HOST,
        rpc_http=RPC_HTTP_PORT,
        ui_static=UI_STATIC_PATH,
        ui_path=UI_PATH,
        rpc_ws=RPC_WS_PORT,
        grpc=GRPC_PORT,
        mnemonic=mnemonic,
    )


def postgres_init_sql() -> str:
    """The script the Postgres container runs once: one database per node."""
    return "".join(f"CREATE DATABASE {node};\n" for node in NODES)
