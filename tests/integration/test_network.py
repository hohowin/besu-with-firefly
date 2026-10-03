"""The network seen through its RPC node: the validator set, zero gas and a moving chain."""

import pytest

from src.adapters.docker_stack import REPO_ROOT, DockerStack
from tests.support.polling import wait_for
from tests.support.rpc import RPC_ANSON, block_number, peer_count, rpc_call

RPC_NODE = "besu-rpc-anson"

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


def test_the_rpc_node_is_running_and_healthy(stack: DockerStack) -> None:
    states = {s.service: s for s in stack.states()}
    assert RPC_NODE in states, f"{RPC_NODE} is not part of the stack"
    assert (states[RPC_NODE].state, states[RPC_NODE].health) == ("running", "healthy")


def test_the_chain_keeps_moving(stack: DockerStack) -> None:
    first = block_number(RPC_ANSON)
    wait_for(
        lambda: block_number(RPC_ANSON) > first or None,
        describe=f"{RPC_NODE} to pass block #{first}",
        timeout=30,
        interval=1,
    )


def test_gas_price_is_zero(stack: DockerStack) -> None:
    assert rpc_call(RPC_ANSON, "eth_gasPrice") == "0x0"


def test_the_validator_set_is_exactly_the_one_validator_and_the_rpc_node_is_not_in_it(
    stack: DockerStack,
) -> None:
    listed = rpc_call(RPC_ANSON, "qbft_getValidatorsByBlockNumber", ["latest"])
    validators = {address.lower() for address in listed}
    assert validators == _validator_addresses(), f"{RPC_NODE} sees {sorted(validators)}"
    assert len(validators) == 1
    node_id = rpc_call(RPC_ANSON, "admin_nodeInfo")["id"].removeprefix("0x").lower()
    assert node_id not in _validator_public_keys(), f"{RPC_NODE} runs a validator key"


def test_the_rpc_node_is_connected_to_the_validator(stack: DockerStack) -> None:
    # An RPC node dials its static peers on a 60 s cycle, so allow a full cycle.
    count = wait_for(
        lambda: peer_count(RPC_ANSON) if peer_count(RPC_ANSON) >= 1 else None,
        describe=f"{RPC_NODE} to report a peer",
        timeout=150,
    )
    assert count >= 1
