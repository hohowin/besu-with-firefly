"""Anson sends Beatrice 40 of his 100, across all three nodes."""

import time

import pytest

from src.adapters.paladin import PALADIN_NODES, PaladinClient, http_transport
from src.adapters.paladin_artifacts import load_noto_private_abi
from src.adapters.paladin_noto import balance_of, deploy_token, mint, transfer
from src.core.paladin.rpc import PaladinRpcError

pytestmark = pytest.mark.integration

ABI = load_noto_private_abi()
ANSON = "anson@node2"
BEATRICE = "beatrice@node3"


@pytest.fixture(scope="module")
def client(deployed: dict[str, str]) -> PaladinClient:
    return PaladinClient(PALADIN_NODES, http_transport())


@pytest.fixture(scope="module")
def token(client: PaladinClient) -> str:
    address = deploy_token(client)
    mint(client, address, ABI, ANSON, 100)
    return address


def wait_for_balance(client: PaladinClient, token: str, account: str, expected: int) -> int:
    """A coin reaches its owner's node a moment after the receipt, so poll briefly."""
    deadline = time.monotonic() + 30
    while True:
        balance = balance_of(client, token, ABI, account)
        if balance == expected or time.monotonic() > deadline:
            return balance
        time.sleep(1)


def test_a_transfer_moves_40_and_leaves_60(client: PaladinClient, token: str) -> None:
    receipt = transfer(client, token, ABI, ANSON, BEATRICE, 40)
    assert receipt["success"] is True
    assert wait_for_balance(client, token, ANSON, 60) == 60
    assert wait_for_balance(client, token, BEATRICE, 40) == 40


def test_a_transfer_larger_than_the_balance_fails_and_changes_nothing(
    client: PaladinClient, token: str
) -> None:
    assert wait_for_balance(client, token, ANSON, 60) == 60
    with pytest.raises(PaladinRpcError):
        transfer(client, token, ABI, ANSON, BEATRICE, 1000)
    assert balance_of(client, token, ABI, ANSON) == 60
    assert balance_of(client, token, ABI, BEATRICE) == 40
