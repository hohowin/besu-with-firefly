"""The three Paladin nodes are registered in the EVM registry, with their gRPC transport."""

import json

import pytest

from src.adapters.addresses import read_addresses
from src.core.paladin.bootstrap import ADDRESS_NAMES
from tests.support.deploy import run_deploy
from tests.support.paladin import PALADIN_PORTS, paladin_call
from tests.support.rpc import RPC_ANSON, rpc_call

pytestmark = pytest.mark.integration

NODES = list(PALADIN_PORTS)


def entries() -> dict[str, dict[str, object]]:
    listed = paladin_call(
        "node1", "reg_queryEntriesWithProps", ["evm-registry", {"limit": 50}, "any"]
    )
    return {entry["name"]: entry for entry in listed}


def registry_log_count() -> int:
    registry = read_addresses()[ADDRESS_NAMES["registry"]]
    logs = rpc_call(RPC_ANSON, "eth_getLogs", [{"address": registry, "fromBlock": "0x0"}])
    return len(logs)


def test_node1_lists_all_three_nodes_in_the_registry(deployed: dict[str, str]) -> None:
    listed = entries()
    assert {"node1", "node2", "node3"} <= set(listed)
    assert all(listed[name]["active"] is True for name in NODES)


@pytest.mark.parametrize("node", NODES)
def test_each_node_has_published_its_grpc_endpoint(deployed: dict[str, str], node: str) -> None:
    properties = entries()[node]["properties"]
    assert isinstance(properties, dict)
    transport = json.loads(properties["transport.grpc"])
    assert transport["endpoint"] == f"dns:///paladin-{node}:9000"
    assert "BEGIN CERTIFICATE" in transport["issuers"]


@pytest.mark.parametrize("node", NODES)
def test_each_entry_is_owned_by_that_nodes_own_registry_key(
    deployed: dict[str, str], node: str
) -> None:
    key = paladin_call(
        node, "keymgr_resolveKey", [f"registry.{node}", "ecdsa:secp256k1", "eth_address"]
    )
    properties = entries()[node]["properties"]
    assert isinstance(properties, dict)
    assert properties["$owner"].lower() == key["verifier"]["verifier"].lower()


@pytest.mark.parametrize("node", NODES)
def test_every_node_sees_the_same_registry(deployed: dict[str, str], node: str) -> None:
    from_node = paladin_call(
        node, "reg_queryEntriesWithProps", ["evm-registry", {"limit": 50}, "any"]
    )
    assert {entry["name"] for entry in from_node} >= {"node1", "node2", "node3"}


def test_running_deploy_again_sends_no_registry_transaction(deployed: dict[str, str]) -> None:
    before = registry_log_count()
    assert before >= 6  # three registrations and three transports
    result = run_deploy()
    assert result.returncode == 0, result.stderr
    assert registry_log_count() == before
