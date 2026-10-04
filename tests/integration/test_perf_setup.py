"""`stack.py perf-setup` against the live stack: verified wallets that hold COIN."""

import json
from collections.abc import Iterator

import pytest

from src.adapters.docker_stack import REPO_ROOT
from src.adapters.perf_setup import perf_setup
from src.core.perf.wallets import benchmark_wallets
from src.core.trex.amounts import to_base_units
from tests.support.firefly import ff_post

pytestmark = pytest.mark.integration

NS = "/api/v1/namespaces/default"
WALLETS = benchmark_wallets(2)  # 4 wallets: 2 per layer
COINS = 10


def query(api: str, method: str, inputs: dict[str, str]) -> object:
    return ff_post(f"{NS}/apis/{api}/query/{method}", {"input": inputs})["output"]


def balance(address: str) -> int:
    return int(str(query("coin", "balanceOf", {"_userAddress": address})))


def total_supply() -> int:
    return int(str(ff_post(f"{NS}/apis/coin/query/totalSupply", {})["output"]))


def admin_address() -> str:
    document = json.loads((REPO_ROOT / "network-config" / "wallets.json").read_text("utf-8"))
    return str(next(w["address"] for w in document["wallets"] if w["name"] == "admin"))


@pytest.fixture
def burned_afterwards(deployed: dict[str, str]) -> Iterator[None]:
    """Funding mints new COIN, which would break the supply tests (1000 in all), so burn it."""
    yield
    for wallet in WALLETS:
        held = balance(wallet.address)
        if held:
            ff_post(
                f"{NS}/apis/coin/invoke/burn?confirm=true",
                {
                    "input": {"_userAddress": wallet.address, "_amount": str(held)},
                    "key": admin_address(),
                },
                timeout=120,
            )
        assert balance(wallet.address) == 0


def test_perf_setup_makes_wallets_verified_with_coins_and_a_second_run_sends_nothing(
    burned_afterwards: None,
) -> None:
    seconds = perf_setup(REPO_ROOT / "network-config", 2, COINS, log=lambda _m: None)
    assert seconds > 0
    for wallet in WALLETS:
        assert query("identity-registry", "isVerified", {"_userAddress": wallet.address}) is True
        assert balance(wallet.address) >= to_base_units(COINS)

    again: list[str] = []
    perf_setup(REPO_ROOT / "network-config", 2, COINS, log=again.append)
    assert [line.split()[0] for line in again] == ["signer", "perf-setup"]  # no write was logged
