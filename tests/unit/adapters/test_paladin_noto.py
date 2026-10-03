"""The Noto adapter sends each call to the node that owns the identity."""

from collections.abc import Mapping
from typing import Any

import pytest

from src.adapters.paladin_noto import balance_of, coin_states, deploy_token, mint, transfer

TOKEN = "0x" + "cd" * 20
ABI: list[dict[str, Any]] = [{"type": "function", "name": "x"}]


class FakeClient:
    def __init__(self, receipt: dict[str, Any] | None = None, reply: Any = None) -> None:
        self.sent: list[tuple[str, Mapping[str, Any]]] = []
        self.calls: list[tuple[str, Mapping[str, Any]]] = []
        self._receipt = receipt if receipt is not None else {"contractAddress": TOKEN}
        self._reply = reply if reply is not None else {"totalBalance": "60", "overflow": False}

    def send_and_wait(self, node: str, transaction: Mapping[str, Any]) -> dict[str, Any]:
        self.sent.append((node, transaction))
        return self._receipt

    def private_call(self, node: str, call: Mapping[str, Any]) -> Any:
        self.calls.append((node, call))
        return self._reply


def test_deploy_goes_through_node1_and_returns_the_address() -> None:
    client = FakeClient()
    assert deploy_token(client) == TOKEN
    assert client.sent[0][0] == "node1"
    assert client.sent[0][1]["data"]["notary"] == "notary@node1"


def test_deploy_without_an_address_is_an_error() -> None:
    with pytest.raises(RuntimeError, match="contractAddress"):
        deploy_token(FakeClient(receipt={"success": True}))


def test_mint_is_submitted_on_node1() -> None:
    client = FakeClient()
    mint(client, TOKEN, ABI, "anson@node2", 100)
    node, request = client.sent[0]
    assert node == "node1"
    assert request["function"] == "mint"
    assert request["data"]["to"] == "anson@node2"


def test_transfer_is_submitted_on_the_senders_node() -> None:
    client = FakeClient()
    transfer(client, TOKEN, ABI, "anson@node2", "beatrice@node3", 40)
    node, request = client.sent[0]
    assert node == "node2"
    assert request["from"] == "anson@node2"


def test_balance_is_asked_of_the_accounts_node() -> None:
    client = FakeClient()
    assert balance_of(client, TOKEN, ABI, "beatrice@node3") == 60
    assert client.calls[0][0] == "node3"


class FakeReader:
    def __init__(self) -> None:
        self.asked: list[tuple[str, str, list[Any]]] = []

    def call(self, node: str, method: str, params: list[Any] | None = None) -> Any:
        assert params is not None
        self.asked.append((node, method, params))
        if method == "pstate_listSchemas":
            return [{"id": "s1"}, {"id": "s2"}]
        return [{"id": f"state-of-{params[2]}"}]


def test_coin_states_gathers_every_schema_of_the_token_on_that_node() -> None:
    reader = FakeReader()
    states = coin_states(reader, "node3", TOKEN)
    assert [s["id"] for s in states] == ["state-of-s1", "state-of-s2"]
    assert {node for node, _, _ in reader.asked} == {"node3"}
    assert reader.asked[1][2][:3] == ["noto", TOKEN, "s1"]
