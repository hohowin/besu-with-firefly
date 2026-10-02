from collections.abc import Mapping
from typing import Any

from src.adapters.trex_onboard import mint_initial_supply
from src.core.firefly.operations import Operation
from src.core.trex.amounts import to_base_units

ADMIN = "0x" + "aa" * 20
ANSON = "0x" + "a1" * 20
ACCOUNTS = {"admin": ADMIN, "anson": ANSON}


class FakeToken:
    def __init__(self, supply: int = 0) -> None:
        self.supply = supply
        self.writes: list[tuple[str, str, dict[str, Any], str | None, str | None]] = []

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        assert (api, method) == ("coin", "totalSupply")
        return str(self.supply)

    def api_invoke(self, api: str, method: str, inputs: Mapping[str, Any], key: str | None = None,
                   idempotency_key: str | None = None, timeout: float = 0) -> Operation:
        self.writes.append((api, method, dict(inputs), key, idempotency_key))
        self.supply += int(inputs["_amount"])
        return Operation("op", "Succeeded")

    def transaction_operations(self, transaction_id: str) -> list[Operation]:
        return [Operation("op-old", "Succeeded")]


def run(token: FakeToken) -> None:
    mint_initial_supply(token, ACCOUNTS, lambda _line: None, sleep=lambda _s: None)


def test_one_thousand_coins_are_minted_to_anson_by_admin() -> None:
    token = FakeToken()
    run(token)
    inputs = {"_to": ANSON, "_amount": str(to_base_units(1000))}
    assert token.writes == [("coin", "mint", inputs, ADMIN, "trex-mint-anson")]


def test_a_second_run_mints_nothing() -> None:
    token = FakeToken()
    run(token)
    run(token)
    assert len(token.writes) == 1


def test_nothing_is_minted_when_the_supply_is_already_there() -> None:
    token = FakeToken(supply=to_base_units(1000))
    run(token)
    assert token.writes == []
