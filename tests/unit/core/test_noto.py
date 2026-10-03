"""Request builders for the private Noto calls."""

import pytest

from src.core.paladin.noto import (
    NOTARY,
    balance_call,
    balance_from,
    deploy_request,
    identity,
    mint_request,
    transfer_request,
)

TOKEN = "0x" + "ab" * 20
ABI = [{"type": "function", "name": "mint"}]


def test_identity_joins_name_and_node() -> None:
    assert identity("anson", "node2") == "anson@node2"


def test_deploy_names_the_notary_with_a_constructor_abi() -> None:
    request = deploy_request()
    assert request["type"] == "private"
    assert request["domain"] == "noto"
    assert request["from"] == NOTARY == "notary@node1"
    assert request["data"] == {"notary": NOTARY, "notaryMode": "basic"}
    constructor = request["abi"][0]
    assert constructor["type"] == "constructor"
    assert [i["name"] for i in constructor["inputs"]] == ["notary", "notaryMode"]
    assert "to" not in request


def test_mint_is_sent_by_the_notary_to_the_token() -> None:
    request = mint_request(TOKEN, ABI, "anson@node2", 100)
    assert request["type"] == "private"
    assert request["domain"] == "noto"
    assert request["from"] == NOTARY
    assert request["to"] == TOKEN
    assert request["abi"] == ABI
    assert request["function"] == "mint"
    assert request["data"] == {"to": "anson@node2", "amount": 100, "data": "0x"}


def test_transfer_is_sent_by_the_sender() -> None:
    request = transfer_request(TOKEN, ABI, "anson@node2", "beatrice@node3", 40)
    assert request["from"] == "anson@node2"
    assert request["function"] == "transfer"
    assert request["data"] == {"to": "beatrice@node3", "amount": 40, "data": "0x"}


def test_balance_call_asks_for_the_account() -> None:
    call = balance_call(TOKEN, ABI, "anson@node2")
    assert call["function"] == "balanceOf"
    assert call["from"] == "anson@node2"
    assert call["to"] == TOKEN
    assert call["data"] == {"account": "anson@node2"}


@pytest.mark.parametrize(
    ("value", "expected"),
    [(100, 100), ("100", 100), ("0x64", 100), ("0", 0)],
)
def test_balance_from_accepts_numbers_in_any_form(value: object, expected: int) -> None:
    assert balance_from({"totalStates": "1", "totalBalance": value, "overflow": False}) == expected


def test_balance_from_refuses_an_overflowing_balance() -> None:
    with pytest.raises(ValueError, match="overflow"):
        balance_from({"totalStates": "9", "totalBalance": "5", "overflow": True})


def test_balance_from_refuses_a_reply_without_a_balance() -> None:
    with pytest.raises(ValueError, match="totalBalance"):
        balance_from({"totalStates": "0"})


@pytest.mark.parametrize("amount", [0, -1])
def test_amounts_must_be_positive(amount: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        mint_request(TOKEN, ABI, "anson@node2", amount)
    with pytest.raises(ValueError, match="positive"):
        transfer_request(TOKEN, ABI, "anson@node2", "beatrice@node3", amount)
