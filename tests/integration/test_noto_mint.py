"""A Noto token is deployed through node1 and minted to Anson on node2 (mutual TLS)."""

import subprocess
import time

import pytest

from src.adapters.paladin import PALADIN_NODES, PaladinClient, http_transport
from src.adapters.paladin_artifacts import load_noto_private_abi
from src.adapters.paladin_noto import balance_of, deploy_token, mint

pytestmark = pytest.mark.integration

ABI = load_noto_private_abi()
ANSON = "anson@node2"


@pytest.fixture(scope="module")
def client(deployed: dict[str, str]) -> PaladinClient:
    return PaladinClient(PALADIN_NODES, http_transport())


@pytest.fixture(scope="module")
def minted(client: PaladinClient) -> str:
    token = deploy_token(client)
    mint(client, token, ABI, ANSON, 100)
    return token


def wait_for_balance(client: PaladinClient, token: str, account: str, expected: int) -> int:
    """The coin reaches the owner's node a moment after the receipt, so poll briefly."""
    deadline = time.monotonic() + 30
    while True:
        balance = balance_of(client, token, ABI, account)
        if balance == expected or time.monotonic() > deadline:
            return balance
        time.sleep(1)


def container_log(name: str) -> str:
    result = subprocess.run(
        ["docker", "logs", name], capture_output=True, text=True, check=True, timeout=60
    )
    return result.stdout + result.stderr


def test_the_token_has_an_address_known_to_every_node(client: PaladinClient, minted: str) -> None:
    assert minted.startswith("0x") and len(minted) == 42
    for node in ("node1", "node2", "node3"):
        # A node that does not know the token fails this call instead of answering 0.
        assert balance_of(client, minted, ABI, f"nobody@{node}") == 0


def test_anson_holds_the_minted_100_on_his_own_node(client: PaladinClient, minted: str) -> None:
    assert wait_for_balance(client, minted, ANSON, 100) == 100


def test_nodes_talked_over_mutual_tls(client: PaladinClient, minted: str) -> None:
    wait_for_balance(client, minted, ANSON, 100)
    assert "TLS handshake completed" in container_log("paladin-node1")
    assert "TLS handshake completed" in container_log("paladin-node2")


def test_a_second_token_is_independent(client: PaladinClient, minted: str) -> None:
    other = deploy_token(client)
    assert other != minted
    assert balance_of(client, other, ABI, ANSON) == 0
    assert balance_of(client, minted, ABI, ANSON) == 100
