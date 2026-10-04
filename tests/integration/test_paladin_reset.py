"""A plain restart keeps Paladin's keys and state (the key-derivation hazard from the spike)."""

from functools import partial

import pytest

from src.adapters.docker_stack import DockerStack
from src.adapters.paladin import PALADIN_NODES, PaladinClient, http_transport
from src.adapters.paladin_artifacts import load_noto_private_abi
from src.adapters.paladin_noto import balance_of, deploy_token, mint
from tests.support.paladin import paladin_call
from tests.support.polling import wait_for

pytestmark = pytest.mark.integration

ABI = load_noto_private_abi()
NODES = ("node1", "node2", "node3")
ANSON = "anson@node2"


def key_address(node: str, name: str) -> str:
    key = paladin_call(node, "keymgr_resolveKey", [name, "ecdsa:secp256k1", "eth_address"])
    return str(key["verifier"]["verifier"]).lower()


def noto_loaded(node: str) -> bool:
    return bool(paladin_call(node, "domain_listDomains") == ["noto"])


def registered() -> set[str]:
    entries = paladin_call(
        "node1", "reg_queryEntriesWithProps", ["evm-registry", {"limit": 50}, "any"]
    )
    return {entry["name"] for entry in entries}


def test_after_a_plain_restart_keys_registry_and_balances_are_unchanged(
    stack: DockerStack, deployed: dict[str, str]
) -> None:
    client = PaladinClient(PALADIN_NODES, http_transport())
    token = deploy_token(client)
    mint(client, token, ABI, ANSON, 100)
    wait_for(lambda: balance_of(client, token, ABI, ANSON) == 100, describe="Anson to hold 100")

    keys_before = {
        "registry.operator": key_address("node1", "registry.operator"),
        **{f"registry.{node}": key_address(node, f"registry.{node}") for node in NODES},
    }
    assert registered() >= set(NODES)

    for node in NODES:
        stack.restart(f"paladin-{node}")
    for node in NODES:  # `domain_listDomains` answers only once the node has finished starting
        wait_for(
            partial(noto_loaded, node),
            describe=f"{node} to load the Noto domain again",
            timeout=180,
        )

    assert key_address("node1", "registry.operator") == keys_before["registry.operator"]
    for node in NODES:
        assert key_address(node, f"registry.{node}") == keys_before[f"registry.{node}"]
    assert registered() >= set(NODES)
    assert (
        wait_for(
            lambda: balance_of(client, token, ABI, ANSON), describe="Anson's balance", timeout=60
        )
        == 100
    )
