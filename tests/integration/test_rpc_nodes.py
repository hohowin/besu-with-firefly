"""The two RPC nodes: they join the network, agree on the chain and are not validators."""

import time
from functools import partial

import pytest

from src.adapters.docker_stack import REPO_ROOT, DockerStack
from tests.support.polling import wait_for
from tests.support.rpc import RPC_ANSON, RPC_BEATRICE, block_number, peer_count, rpc_call

RPC_NODES = {"besu-rpc-anson": RPC_ANSON, "besu-rpc-beatrice": RPC_BEATRICE}

pytestmark = pytest.mark.integration


def _validator_addresses() -> set[str]:
    keys = REPO_ROOT / "network-config" / "validator-keys"
    return {
        p.read_text(encoding="utf-8").strip().lower()
        for p in sorted(keys.glob("validator-*/address.txt"))
    }


def _validator_public_keys() -> set[str]:
    keys = REPO_ROOT / "network-config" / "validator-keys"
    return {
        p.read_text(encoding="utf-8").strip().removeprefix("0x").lower()
        for p in keys.glob("validator-*/key.pub")
    }


def test_both_rpc_nodes_are_running_and_healthy(stack: DockerStack) -> None:
    states = {s.service: s for s in stack.states()}
    for name in RPC_NODES:
        assert name in states, f"{name} is not part of the stack"
        assert (states[name].state, states[name].health) == ("running", "healthy"), name


def test_rpc_nodes_agree_within_one_block(stack: DockerStack) -> None:
    def past_genesis(url: str) -> bool:
        return block_number(url) >= 1

    for name, url in RPC_NODES.items():
        wait_for(partial(past_genesis, url), describe=f"{name} past block 0")
    time.sleep(5)
    anson, beatrice = block_number(RPC_ANSON), block_number(RPC_BEATRICE)
    assert abs(anson - beatrice) <= 1, f"anson at #{anson}, beatrice at #{beatrice}"


@pytest.mark.parametrize("name", RPC_NODES)
def test_gas_price_is_zero(stack: DockerStack, name: str) -> None:
    assert rpc_call(RPC_NODES[name], "eth_gasPrice") == "0x0", name


@pytest.mark.parametrize("name", RPC_NODES)
def test_rpc_node_is_not_a_validator(stack: DockerStack, name: str) -> None:
    url = RPC_NODES[name]
    listed = rpc_call(url, "qbft_getValidatorsByBlockNumber", ["latest"])
    validators = {address.lower() for address in listed}
    assert validators == _validator_addresses(), f"{name} sees {sorted(validators)}"
    node_id = rpc_call(url, "admin_nodeInfo")["id"].removeprefix("0x").lower()
    assert node_id not in _validator_public_keys(), f"{name} runs a validator key"


@pytest.mark.parametrize("name", RPC_NODES)
def test_rpc_node_has_at_least_four_peers(stack: DockerStack, name: str) -> None:
    url = RPC_NODES[name]
    count = wait_for(
        lambda: peer_count(url) if peer_count(url) >= 4 else None,
        describe=f"{name} to report 4 or more peers",
        timeout=90,
    )
    assert count >= 4, name
