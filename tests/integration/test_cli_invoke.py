"""`besu-ff invoke` against the live stack: a compliant transfer and a refused one."""

import json
import urllib.error

import pytest

from src.adapters.docker_stack import REPO_ROOT
from src.adapters.ff_cli import main
from src.core.trex.amounts import to_base_units
from tests.support.firefly import ff_post

pytestmark = pytest.mark.integration

NS = "/api/v1/namespaces/default"
REASON = "Transfer not possible"


def wallets() -> dict[str, str]:
    document = json.loads((REPO_ROOT / "network-config" / "wallets.json").read_text("utf-8"))
    return {w["name"]: w["address"] for w in document["wallets"]}


def balance(address: str) -> int:
    answer = ff_post(f"{NS}/apis/coin/query/balanceOf", {"input": {"_userAddress": address}})
    return int(answer["output"])


def transfer_args(recipient: str, coins: int) -> list[str]:
    return [
        "invoke", "transfer", "--contract", "coin", "--as", "anson",
        "--input", f"_to=@{recipient}", "--input", f"_amount={to_base_units(coins)}",
    ]  # fmt: skip


def test_anson_transfers_to_beatrice_and_both_balances_move(
    deployed: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    accounts = wallets()
    anson, beatrice = balance(accounts["anson"]), balance(accounts["beatrice"])
    assert main(transfer_args("beatrice", 1)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "sent       transfer as anson"
    assert lines[1].startswith("operation  ")
    amount = to_base_units(1)
    assert balance(accounts["anson"]) == anson - amount
    assert balance(accounts["beatrice"]) == beatrice + amount
    assert f"balance    anson  {anson - amount}" in lines
    assert f"balance    beatrice  {beatrice + amount}" in lines


def test_a_transfer_to_the_unverified_admin_is_refused_by_the_contract(
    deployed: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    accounts = wallets()
    before = {name: balance(address) for name, address in accounts.items()}
    assert main(transfer_args("admin", 1)) == 1
    captured = capsys.readouterr()
    assert captured.err == f"error: refused by the contract: {REASON}\n"
    assert "balances unchanged" in captured.out and "sent" not in captured.out
    assert {name: balance(address) for name, address in accounts.items()} == before

    # The same revert comes from FireFly's own API, with no CLI in between.
    body = {"input": {"_to": accounts["admin"], "_amount": str(to_base_units(1))},
            "key": accounts["anson"]}  # fmt: skip
    with pytest.raises(urllib.error.HTTPError) as direct:
        ff_post(f"{NS}/apis/coin/invoke/transfer?confirm=true", body, timeout=120)
    assert REASON in direct.value.read().decode()
