"""The compliance guarantee: the contract refuses a transfer to an unverified recipient."""

import json
import urllib.error
import urllib.request
from typing import Any

import pytest
from eth_abi.abi import decode, encode
from eth_utils.crypto import keccak

from src.adapters.docker_stack import REPO_ROOT
from src.adapters.firefly import FireflyClient, Reverted, http_transport
from src.core.trex.amounts import from_base_units, to_base_units
from tests.support.firefly import FIREFLY, ff_get, ff_post
from tests.support.polling import wait_for
from tests.support.rpc import RPC_ANSON, rpc_call

pytestmark = pytest.mark.integration

NS = "/api/v1/namespaces/default"
REASON = "Transfer not possible"


def wallets() -> dict[str, str]:
    document = json.loads((REPO_ROOT / "network-config" / "wallets.json").read_text("utf-8"))
    return {w["name"]: w["address"] for w in document["wallets"]}


def balance(address: str) -> int:
    answer = ff_post(f"{NS}/apis/coin/query/balanceOf", {"input": {"_userAddress": address}})
    return from_base_units(answer["output"])


def total_supply() -> int:
    return from_base_units(ff_post(f"{NS}/apis/coin/query/totalSupply", {})["output"])


def is_verified(address: str) -> bool:
    path = f"{NS}/apis/identity-registry/query/isVerified"
    return bool(ff_post(path, {"input": {"_userAddress": address}})["output"])


def plain_http_transfer(sender: str, recipient: str, coins: int) -> tuple[int, str]:
    """Call FireFly's generated API with nothing of ours in between, and return what it says."""
    body = {"input": {"_to": recipient, "_amount": str(to_base_units(coins))}, "key": sender}
    request = urllib.request.Request(
        f"{FIREFLY}{NS}/apis/coin/invoke/transfer?confirm=true",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def snapshot(accounts: dict[str, str]) -> dict[str, int]:
    return {name: balance(address) for name, address in accounts.items()} | {
        "supply": total_supply()
    }


def test_admin_is_not_verified(deployed: dict[str, str]) -> None:
    assert is_verified(wallets()["admin"]) is False


def test_a_transfer_to_the_unverified_admin_is_rejected_with_the_contracts_reason(
    deployed: dict[str, str],
) -> None:
    accounts = wallets()
    before = snapshot(accounts)
    client = FireflyClient(http_transport())
    with pytest.raises(Reverted) as raised:
        client.api_invoke(
            "coin",
            "transfer",
            {"_to": accounts["admin"], "_amount": str(to_base_units(10))},
            key=accounts["anson"],
        )
    assert raised.value.reason == REASON
    assert snapshot(accounts) == before, "a rejected transfer must change no balance"


def test_the_same_rejection_comes_from_fireflys_api_called_directly(
    deployed: dict[str, str],
) -> None:
    accounts = wallets()
    before = snapshot(accounts)
    status, text = plain_http_transfer(accounts["anson"], accounts["admin"], 10)
    assert status == 500, text
    assert "EVM reverted" in text and REASON in text
    assert snapshot(accounts) == before


def test_fireflys_record_of_the_attempt_is_a_failed_operation_with_the_revert_text(
    deployed: dict[str, str],
) -> None:
    accounts = wallets()
    plain_http_transfer(accounts["anson"], accounts["admin"], 10)

    def failed_transfer() -> dict[str, Any] | None:
        for op in ff_get(f"{NS}/operations?type=blockchain_invoke&limit=100"):
            if op["status"] == "Failed" and REASON in str(op.get("error")):
                return dict(op)
        return None

    operation = wait_for(failed_transfer, describe="a Failed transfer operation", timeout=30)
    assert "EVM reverted" in operation["error"]


def test_the_contract_itself_refuses_without_firefly_in_the_way(deployed: dict[str, str]) -> None:
    """`eth_call` straight to Besu: Anson to Admin reverts, Anson to Beatrice would succeed."""
    accounts = wallets()
    token = deployed["token"]
    selector = keccak(text="transfer(address,uint256)")[:4]

    def call(recipient: str) -> str:
        data = selector + encode(["address", "uint256"], [recipient, to_base_units(1)])
        params = [{"from": accounts["anson"], "to": token, "data": "0x" + data.hex()}, "latest"]
        return str(rpc_call(RPC_ANSON, "eth_call", params))

    assert int(call(accounts["beatrice"]), 16) == 1  # returns true

    with pytest.raises(RuntimeError, match="revert") as raised:
        call(accounts["admin"])
    error_data = str(raised.value).split("'data': '")[1].split("'")[0]
    assert error_data.startswith("0x08c379a0")  # Error(string)
    (reason,) = decode(["string"], bytes.fromhex(error_data[10:]))
    assert reason == REASON
