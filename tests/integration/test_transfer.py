"""COIN balances after onboarding, and a compliant transfer from Anson to Beatrice."""

import json
from typing import Any

import pytest

from src.adapters.docker_stack import REPO_ROOT
from src.core.trex.amounts import from_base_units, to_base_units
from tests.support.firefly import ff_get, ff_post

pytestmark = pytest.mark.integration

NS = "/api/v1/namespaces/default"


def wallets() -> dict[str, str]:
    document = json.loads((REPO_ROOT / "network-config" / "wallets.json").read_text("utf-8"))
    return {w["name"]: w["address"] for w in document["wallets"]}


def balance(address: str) -> int:
    answer = ff_post(f"{NS}/apis/coin/query/balanceOf", {"input": {"_userAddress": address}})
    return from_base_units(answer["output"])


def total_supply() -> int:
    return from_base_units(ff_post(f"{NS}/apis/coin/query/totalSupply", {})["output"])


def transfer(sender: str, recipient: str, coins: int) -> dict[str, Any]:
    operation: dict[str, Any] = ff_post(
        f"{NS}/apis/coin/invoke/transfer?confirm=true",
        {"input": {"_to": recipient, "_amount": str(to_base_units(coins))}, "key": sender},
        timeout=120,
    )
    return operation


def test_right_after_a_fresh_deploy_anson_holds_1000_and_beatrice_0(
    deployed: dict[str, str],
) -> None:
    """Exact only while no transfer has happened since the last reset, so it skips afterwards."""
    operations = ff_get(f"{NS}/operations?type=blockchain_invoke&limit=500")
    if any('"name": "transfer"' in json.dumps(op["input"]) for op in operations):
        pytest.skip("a transfer already happened on this chain; the invariants above still hold")
    accounts = wallets()
    assert balance(accounts["anson"]) == 1000
    assert balance(accounts["beatrice"]) == 0


def test_one_thousand_coin_exist_and_all_of_it_is_held_by_the_investors(
    deployed: dict[str, str],
) -> None:
    accounts = wallets()
    assert total_supply() == 1000
    assert balance(accounts["admin"]) == 0
    assert balance(accounts["anson"]) + balance(accounts["beatrice"]) == 1000


def test_a_transfer_from_anson_to_beatrice_moves_exactly_the_amount(
    deployed: dict[str, str],
) -> None:
    accounts = wallets()
    anson_before, beatrice_before = balance(accounts["anson"]), balance(accounts["beatrice"])
    operation = transfer(accounts["anson"], accounts["beatrice"], 25)
    assert operation["status"] == "Succeeded"
    assert balance(accounts["anson"]) == anson_before - 25
    assert balance(accounts["beatrice"]) == beatrice_before + 25
    assert total_supply() == 1000
