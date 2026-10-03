"""Noto keeps coins private: each node sees only its own, and the chain shows no amounts."""

import time

import pytest

from src.adapters.paladin import PALADIN_NODES, PaladinClient, http_transport
from src.adapters.paladin_artifacts import load_noto_private_abi
from src.adapters.paladin_noto import coin_states, deploy_token, mint, transfer
from src.core.paladin.privacy import coin_amounts, find_leaks, visibility_problems
from tests.support.rpc import RPC_ANSON, rpc_call

pytestmark = pytest.mark.integration

ABI = load_noto_private_abi()
NODES = ("node1", "node2", "node3")
ANSON = "anson@node2"
BEATRICE = "beatrice@node3"


@pytest.fixture(scope="module")
def client(deployed: dict[str, str]) -> PaladinClient:
    return PaladinClient(PALADIN_NODES, http_transport())


@pytest.fixture(scope="module")
def token(client: PaladinClient) -> str:
    return deploy_token(client)


def seen_by_nodes(client: PaladinClient, token: str) -> dict[str, list[int]]:
    return {node: coin_amounts(coin_states(client, node, token)) for node in NODES}


def settle(client: PaladinClient, token: str, expected: dict[str, list[int]]) -> list[str]:
    """Coins reach the other nodes a moment after the receipt. Poll, then report differences."""
    deadline = time.monotonic() + 30
    while True:
        problems = visibility_problems(seen_by_nodes(client, token), expected)
        if not problems or time.monotonic() > deadline:
            return problems
        time.sleep(1)


def address_of(client: PaladinClient, identity: str) -> str:
    name, node = identity.split("@")
    key = client.call(node, "keymgr_resolveKey", [name, "ecdsa:secp256k1", "eth_address"])
    return str(key["verifier"]["verifier"])


def test_after_the_mint_the_third_node_sees_no_coin(client: PaladinClient, token: str) -> None:
    mint(client, token, ABI, ANSON, 100)
    expected = {"node1": [100], "node2": [100], "node3": []}
    assert settle(client, token, expected) == []
    time.sleep(5)  # a leak would arrive shortly after the others
    assert visibility_problems(seen_by_nodes(client, token), expected) == []


def test_after_the_transfer_node3_sees_only_its_own_coin(client: PaladinClient, token: str) -> None:
    transfer(client, token, ABI, ANSON, BEATRICE, 40)
    expected = {"node1": [40, 60, 100], "node2": [40, 60, 100], "node3": [40]}
    assert settle(client, token, expected) == []


def test_the_public_chain_shows_no_amounts_and_no_party_addresses(
    client: PaladinClient, token: str
) -> None:
    logs = rpc_call(RPC_ANSON, "eth_getLogs", [{"address": token, "fromBlock": "0x0"}])
    assert logs, "the token should have emitted logs"
    parties = [address_of(client, ANSON), address_of(client, BEATRICE)]
    assert find_leaks(logs, amounts=[100, 60, 40], addresses=parties) == []
