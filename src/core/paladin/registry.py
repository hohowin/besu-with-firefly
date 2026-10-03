"""What is still missing in the Paladin EVM registry (pure decisions, no I/O).

The Paladin operator registers a node in two steps: node1's registry admin key registers the
identity (`registerIdentity`), then the node itself publishes how to reach it by setting the
`transport.grpc` property (`setIdentityProperty`) with its own key. Both are decided from what
`reg_queryEntriesWithProps` already shows, so a second run sends nothing.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

TRANSPORT_PROPERTY = "transport.grpc"
ZERO_HASH = "0x" + "00" * 32  # the parent of a top-level identity
REGISTRY_NAME = "evm-registry"
ROOT_ENTRY = "root"


@dataclass(frozen=True)
class RegisterNode:
    name: str


@dataclass(frozen=True)
class SetTransport:
    name: str


def registry_steps(
    nodes: Sequence[str],
    entries: Sequence[Mapping[str, Any]],
    local_details: Mapping[str, str],
) -> list[RegisterNode | SetTransport]:
    """The steps still needed: first every missing identity, then every missing or outdated
    transport. `local_details` is what each node says about itself
    (`transport_localTransportDetails`).
    """
    for node in nodes:
        if node not in local_details:
            raise ValueError(f"no transport details for {node}")
    by_name = {str(entry["name"]): entry for entry in entries if entry["name"] != ROOT_ENTRY}
    registrations: list[RegisterNode | SetTransport] = [
        RegisterNode(node) for node in nodes if node not in by_name
    ]
    transports: list[RegisterNode | SetTransport] = []
    for node in nodes:
        entry = by_name.get(node)
        current = None if entry is None else entry.get("properties", {}).get(TRANSPORT_PROPERTY)
        if current != local_details[node]:
            transports.append(SetTransport(node))
    return registrations + transports
