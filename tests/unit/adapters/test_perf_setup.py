import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from src.adapters.perf_setup import mint_to_wallets, perf_setup
from src.core.firefly.operations import Operation
from src.core.network.wallets import Wallet
from src.core.perf.wallets import derive_wallets
from src.core.trex.amounts import to_base_units

ADMIN = "0x" + "aa" * 20
ACCOUNTS = {"admin": ADMIN, "perf-001": "0x" + "01" * 20, "perf-002": "0x" + "02" * 20}


class FakeToken:
    def __init__(self, balances: Mapping[str, int] | None = None) -> None:
        self.balances = dict(balances or {})
        self.mints: list[tuple[str, int, str | None, str | None]] = []

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        assert (api, method) == ("coin", "balanceOf")
        return str(self.balances.get(inputs["_userAddress"], 0))

    def api_invoke(
        self,
        api: str,
        method: str,
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = 120.0,
    ) -> Operation:
        assert (api, method) == ("coin", "mint")
        amount = int(inputs["_amount"])
        self.mints.append((inputs["_to"], amount, key, idempotency_key))
        self.balances[inputs["_to"]] = self.balances.get(inputs["_to"], 0) + amount
        return Operation("op", "Succeeded", tx="tx")

    def transaction_operations(self, transaction_id: str) -> list[Operation]:
        return []


def mint(token: FakeToken, coins: int = 100) -> list[str]:
    logged: list[str] = []
    mint_to_wallets(
        token,
        ACCOUNTS,
        ["perf-001", "perf-002"],
        coins,
        logged.append,
        sleep=lambda _s: None,
        clock=lambda: 0.0,
    )
    return logged


def test_each_wallet_is_minted_the_coins_it_is_missing_as_admin() -> None:
    token = FakeToken({ACCOUNTS["perf-002"]: to_base_units(30)})
    mint(token)
    assert [(to, amount, key) for to, amount, key, _ in token.mints] == [
        (ACCOUNTS["perf-001"], to_base_units(100), ADMIN),
        (ACCOUNTS["perf-002"], to_base_units(70), ADMIN),
    ]


def test_a_second_run_mints_nothing() -> None:
    token = FakeToken()
    mint(token)
    token.mints.clear()
    assert mint(token) == []
    assert token.mints == []


def test_the_idempotency_key_names_the_wallet_and_the_state_it_was_sent_from() -> None:
    """A top-up after the balance dropped must not reuse the key of an earlier mint."""
    token = FakeToken()
    mint(token)
    token.balances[ACCOUNTS["perf-001"]] = to_base_units(40)
    token.mints.clear()
    mint(token)
    assert len(token.mints) == 1
    assert token.mints[0][3] == "perf-mint-perf-001-40000000000000000000-100"  # not ...-0-100


def test_perf_setup_loads_wallets_then_registers_then_claims_then_mints(tmp_path: Path) -> None:
    order: list[str] = []
    wallets = {"wallets": [{"name": "admin", "address": ADMIN, "privateKey": "0x" + "11" * 32}]}
    (tmp_path / "wallets.json").write_text(json.dumps(wallets), encoding="utf-8")
    addresses = tmp_path / "addresses.json"
    addresses.write_text(json.dumps({"id-factory": "0xf0"}), encoding="utf-8")
    token = FakeToken()
    seen: dict[str, Any] = {}

    def load_wallets(wallets: Sequence[Wallet]) -> list[str]:
        order.append("load")
        seen["wallets"] = [w.name for w in wallets]
        return []

    def register(
        client: Any, load: Any, addresses: Any, accounts: Any, log: Any, **kw: Any
    ) -> None:
        order.append("register")
        seen["names"] = list(kw["names"])
        seen["accounts"] = dict(accounts)

    def claim(
        client: Any, load: Any, addresses: Any, accounts: Any, key: str, log: Any, **kw: Any
    ) -> None:
        order.append("claim")
        seen["issuer_key"] = key

    ticks = iter([0.0, 12.5])
    seconds = perf_setup(
        tmp_path,
        2,
        100,
        addresses_file=addresses,
        log=lambda _m: None,
        client=token,
        load_wallets=load_wallets,
        register=register,
        claim=claim,
        clock=lambda: next(ticks),
        sleep=lambda _s: None,
    )
    assert order == ["load", "register", "claim"]
    assert seen["wallets"] == seen["names"] == ["perf-001", "perf-002"]
    derived = derive_wallets(2)
    assert seen["accounts"]["perf-002"] == derived[1].address and seen["accounts"]["admin"] == ADMIN
    assert seen["issuer_key"] == "0x" + "11" * 32
    assert [m[0] for m in token.mints] == [derived[0].address, derived[1].address]
    assert seconds == 12.5


def test_perf_setup_refuses_a_stack_that_was_not_deployed(tmp_path: Path) -> None:
    wallets = {"wallets": [{"name": "admin", "address": ADMIN, "privateKey": "0x" + "11" * 32}]}
    (tmp_path / "wallets.json").write_text(json.dumps(wallets), encoding="utf-8")
    with pytest.raises(ValueError, match="deploy"):
        perf_setup(tmp_path, 1, 1, addresses_file=tmp_path / "missing.json", client=FakeToken())

