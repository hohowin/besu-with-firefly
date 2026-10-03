"""The Paladin bootstrap, as pure data and text (no I/O).

Paladin can only be given its Noto domain and registry once their contracts exist, and those are
deployed through Paladin node1 itself. So the nodes start with the base config (no domain), the
contracts are deployed in the order the Paladin operator uses, and then each node's config is
rebuilt as the base plus the two blocks below and the node is restarted.
"""

import re
from typing import Any

# The order the Paladin operator deploys them. The proxy needs the factory and Noto first.
CONTRACT_ORDER = ("registry", "noto", "noto_factory", "noto_factory_proxy")

# Names in `deployed-addresses.json`.
ADDRESS_NAMES = {
    "registry": "paladin-registry",
    "noto": "paladin-noto",
    "noto_factory": "paladin-noto-factory",
    "noto_factory_proxy": "paladin-noto-factory-proxy",
}

FACTORY_INITIALIZE_SELECTOR = "0xc4d66de8"  # initialize(address)
DEPLOY_NODE = "node1"  # registry admin and notary: it owns the registry's root key

_ADDRESS = re.compile(r"[0-9a-f]{40}")

_DOMAIN_AND_REGISTRY = """\
domains:
  noto:
    plugin:
      type: c-shared
      library: /app/domains/libnoto.so
    config:
      factoryVersion: 2
    registryAddress: {factory_proxy}
registries:
  evm-registry:
    plugin:
      type: c-shared
      library: /app/registries/libevm.so
    config:
      contractAddress: {registry}
"""


class ConfigConflict(Exception):
    """The base config already has a domain or registry, so adding them again would duplicate."""


def _address_hex(address: str) -> str:
    body = address.strip().lower().removeprefix("0x")
    if not _ADDRESS.fullmatch(body):
        raise ValueError(f"an address must be 20 bytes (40 hex characters), got {address!r}")
    return body


def initialize_call_data(noto: str) -> str:
    """Call data of `initialize(noto)`: the selector, then the address left-padded to 32 bytes."""
    return FACTORY_INITIALIZE_SELECTOR + "00" * 12 + _address_hex(noto)


def deploy_params(contract: str, deployed: dict[str, str]) -> Any:
    """The constructor data sent with the deployment of `contract`.

    `deployed` maps the contracts deployed so far (`registry`, `noto`, ...) to their addresses.
    """
    if contract == "registry":
        return [False]  # `rootless` is false: the registry has a root owner, node1's key
    if contract in ("noto", "noto_factory"):
        return {}
    if contract == "noto_factory_proxy":
        return [deployed["noto_factory"], initialize_call_data(deployed["noto"])]
    raise ValueError(f"unknown Paladin contract {contract!r}")


def final_config(base: str, *, registry: str, factory_proxy: str) -> str:
    """The node config once the contracts exist: the base plus the Noto domain and the registry.

    The text of `base` is kept as it is. A base that already has either block is a conflict.
    """
    for block in ("domains:", "registries:"):
        if re.search(rf"^{block}", base, re.MULTILINE):
            raise ConfigConflict(f"the base config already has a {block[:-1]} block")
    separator = "" if base.endswith("\n") else "\n"
    return (
        base
        + separator
        + _DOMAIN_AND_REGISTRY.format(
            factory_proxy=_address_hex_prefixed(factory_proxy),
            registry=_address_hex_prefixed(registry),
        )
    )


def _address_hex_prefixed(address: str) -> str:
    return "0x" + _address_hex(address)
