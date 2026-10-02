"""Enode URLs and the fixed addressing plan for the Besu network (pure, no I/O)."""

import ipaddress
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

P2P_PORT = 30303
_PUBLIC_KEY = re.compile(r"[0-9a-f]{128}")


def normalize_public_key(public_key: str) -> str:
    """Return the key as 128 lowercase hex characters, without a 0x prefix."""
    key = public_key.strip().lower().removeprefix("0x")
    if not _PUBLIC_KEY.fullmatch(key):
        raise ValueError(f"a node public key must be 128 hex characters, got {public_key!r}")
    return key


def enode_url(public_key: str, ip: str, port: int = P2P_PORT) -> str:
    """Build `enode://PUBKEY@IP:PORT`."""
    return f"enode://{normalize_public_key(public_key)}@{ip}:{port}"


@dataclass(frozen=True)
class NetworkAddressing:
    """Fixed IPs for the Compose network: a subnet plus a host offset per node."""

    subnet: str = "172.28.0.0/16"
    validator_offsets: tuple[int, ...] = (11, 12, 13, 14)
    rpc_offsets: dict[str, int] = field(default_factory=lambda: {"anson": 21, "beatrice": 22})

    def __post_init__(self) -> None:
        network = ipaddress.ip_network(self.subnet)
        offsets = [*self.validator_offsets, *self.rpc_offsets.values()]
        if len(offsets) != len(set(offsets)):
            raise ValueError(f"node host offsets must be unique, got {offsets}")
        for offset in offsets:
            if ipaddress.ip_address(int(network.network_address) + offset) not in network:
                raise ValueError(f"offset {offset} is outside the subnet {self.subnet}")

    def _ip(self, offset: int) -> str:
        network = ipaddress.ip_network(self.subnet)
        return str(ipaddress.ip_address(int(network.network_address) + offset))

    def validator_ip(self, number: int) -> str:
        """IP of validator `number` (1-based)."""
        if not 1 <= number <= len(self.validator_offsets):
            raise ValueError(
                f"unknown validator {number}, expected 1 to {len(self.validator_offsets)}"
            )
        return self._ip(self.validator_offsets[number - 1])

    def rpc_ip(self, name: str) -> str:
        """IP of the RPC node with the given label (anson or beatrice)."""
        if name not in self.rpc_offsets:
            raise ValueError(
                f"unknown rpc node {name!r}, expected one of {sorted(self.rpc_offsets)}"
            )
        return self._ip(self.rpc_offsets[name])

    def all_ips(self) -> list[str]:
        return [
            *(self.validator_ip(n) for n in range(1, len(self.validator_offsets) + 1)),
            *(self.rpc_ip(name) for name in self.rpc_offsets),
        ]


def static_nodes(public_keys: Sequence[str], addressing: NetworkAddressing) -> list[str]:
    """One enode per validator, in validator order, for `static-nodes.json`."""
    expected = len(addressing.validator_offsets)
    if len(public_keys) != expected:
        raise ValueError(f"expected {expected} validators, got {len(public_keys)} public keys")
    return [
        enode_url(key, addressing.validator_ip(number))
        for number, key in enumerate(public_keys, start=1)
    ]
