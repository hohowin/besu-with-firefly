"""Register the Paladin nodes in the EVM registry, as the Paladin operator does (adapter)."""

import time
from collections.abc import Callable, Mapping
from typing import Any

from src.adapters.paladin_deploy import PaladinBootstrapError, PaladinNode
from src.core.paladin.artifacts import PaladinArtifact
from src.core.paladin.bootstrap import DEPLOY_NODE
from src.core.paladin.config import NODES
from src.core.paladin.registry import (
    REGISTRY_NAME,
    TRANSPORT_PROPERTY,
    ZERO_HASH,
    RegisterNode,
    SetTransport,
    registry_steps,
)
from src.core.paladin.rpc import PaladinRpcError

ADMIN_KEY = "registry.operator"  # node1's key, the registry's root owner


def _entries(client: PaladinNode) -> list[dict[str, Any]]:
    entries = client.call(
        DEPLOY_NODE, "reg_queryEntriesWithProps", [REGISTRY_NAME, {"limit": 100}, "any"]
    )
    return [dict(entry) for entry in entries]


def _wait_for_entries(
    client: PaladinNode,
    names: tuple[str, ...],
    sleep: Callable[[float], None],
    clock: Callable[[], float],
    timeout: float,
) -> dict[str, str]:
    """The registry ids of `names`, once node1 has indexed them.

    A registration is mined before node1's block indexer shows it, so asking straight away can
    miss the entry that was just created.
    """
    deadline = clock() + timeout
    while True:
        ids = {str(entry["name"]): str(entry["id"]) for entry in _entries(client)}
        missing = [name for name in names if name not in ids]
        if not missing:
            return ids
        if clock() >= deadline:
            raise PaladinBootstrapError(
                missing[0], f"not in the registry index {timeout:g}s after it was registered"
            )
        sleep(1.0)


def register_nodes(
    client: PaladinNode,
    load: Callable[[str], PaladinArtifact],
    registry: str,
    log: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    index_timeout: float = 60.0,
) -> None:
    """Register node1 to node3 in the registry and publish each node's gRPC transport details.

    Reads the registry first and sends only what is missing, so a second run sends nothing.
    """
    abi = load("registry").abi
    details = {
        node: str(client.call(node, "transport_localTransportDetails", ["grpc"])) for node in NODES
    }

    def send(node: str, key: str, function: str, data: Mapping[str, Any]) -> None:
        transaction = {
            "type": "public",
            "from": key,
            "to": registry,
            "abi": abi,
            "function": function,
            "data": dict(data),
        }
        try:
            client.send_and_wait(node, transaction)
        except PaladinRpcError as error:
            raise PaladinBootstrapError(node, str(error)) from error

    steps = registry_steps(NODES, _entries(client), details)
    for registration in (s for s in steps if isinstance(s, RegisterNode)):
        owner = client.call(
            registration.name,
            "keymgr_resolveKey",
            [f"registry.{registration.name}", "ecdsa:secp256k1", "eth_address"],
        )
        send(
            DEPLOY_NODE,
            ADMIN_KEY,
            "registerIdentity",
            {
                "parentIdentityHash": ZERO_HASH,
                "name": registration.name,
                "owner": owner["verifier"]["verifier"],
            },
        )
        log(f"paladin registry  registered {registration.name}")

    transports = [s for s in steps if isinstance(s, SetTransport)]
    if transports:
        ids = _wait_for_entries(client, NODES, sleep, clock, index_timeout)
        for transport in transports:
            send(
                transport.name,
                f"registry.{transport.name}",
                "setIdentityProperty",
                {
                    "identityHash": ids[transport.name],
                    "name": TRANSPORT_PROPERTY,
                    "value": details[transport.name],
                },
            )
            log(f"paladin registry  {transport.name} {TRANSPORT_PROPERTY} set")
