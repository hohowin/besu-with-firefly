"""The Noto demo story against an in-memory Paladin."""

from collections.abc import Mapping
from typing import Any

import pytest

from src.adapters.paladin_demo import DemoFailed, NotDeployed, run_noto_demo
from src.core.paladin.bootstrap import ADDRESS_NAMES

TOKEN = "0x" + "99" * 20
DEPLOYED = {name: "0x" + "ab" * 20 for name in ADDRESS_NAMES.values()}


class FakePaladin:
    """Keeps coins as (amount, owner node, spent) and shows each node what Noto would show it."""

    def __init__(self, leak_to_node3: bool = False) -> None:
        self.coins: list[dict[str, Any]] = []
        self.leak_to_node3 = leak_to_node3
        self.sent: list[tuple[str, str]] = []

    def send_and_wait(self, node: str, transaction: Mapping[str, Any]) -> dict[str, Any]:
        function = transaction.get("function")
        self.sent.append((node, str(function)))
        data = transaction["data"]
        if function is None:
            return {"success": True, "contractAddress": TOKEN}
        if function == "mint":
            self.coins.append({"amount": data["amount"], "node": data["to"].split("@")[1]})
        else:
            owner = transaction["from"].split("@")[1]
            spent = next(c for c in self.coins if c["node"] == owner and "spent" not in c)
            spent["spent"] = True
            self.coins.append({"amount": data["amount"], "node": data["to"].split("@")[1]})
            self.coins.append({"amount": spent["amount"] - data["amount"], "node": owner})
        return {"success": True}

    def private_call(self, node: str, call: Mapping[str, Any]) -> Any:
        mine = [c for c in self.coins if c["node"] == node and "spent" not in c]
        return {"totalBalance": str(sum(c["amount"] for c in mine)), "overflow": False}

    def call(self, node: str, method: str, params: list[Any] | None = None) -> Any:
        if method == "pstate_listSchemas":
            return [{"id": "s"}]
        visible = [
            c
            for c in self.coins
            if node == "node1" or node == "node2" or c["node"] == node or self.leak_to_node3
        ]
        return [{"id": str(i), "data": {"amount": str(c["amount"])}} for i, c in enumerate(visible)]


def run(client: FakePaladin, addresses: Mapping[str, str] = DEPLOYED) -> list[str]:
    lines: list[str] = []
    run_noto_demo(
        client,
        abi=[],
        addresses=addresses,
        log=lines.append,
        sleep=lambda _: None,
        clock=iter(range(10_000)).__next__,
    )
    return lines


def test_the_story_mints_100_then_transfers_40() -> None:
    client = FakePaladin()
    run(client)
    assert client.sent == [("node1", "None"), ("node1", "mint"), ("node2", "transfer")]


def test_it_prints_both_balances_and_what_each_node_sees() -> None:
    text = "\n".join(run(FakePaladin()))
    assert TOKEN in text
    assert "anson@node2" in text and "60" in text
    assert "beatrice@node3" in text and "40" in text
    assert "node3" in text and "[40]" in text
    assert "[40, 60, 100]" in text


def test_a_stack_without_deploy_is_refused_before_anything_is_sent() -> None:
    client = FakePaladin()
    with pytest.raises(NotDeployed, match="deploy"):
        run(client, addresses={})
    assert client.sent == []


def test_a_coin_visible_to_a_non_party_fails_the_demo() -> None:
    with pytest.raises(DemoFailed, match="leak"):
        run(FakePaladin(leak_to_node3=True))
