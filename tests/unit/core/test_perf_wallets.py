import pytest

from src.core.network.wallets import verify_wallet
from src.core.perf.wallets import PERF_SEED, benchmark_wallets, derive_wallets

# Printed by `node perf/lib/derive.js "besu-with-firefly perf demo seed" 3`, which makes the same
# call as Caliper's Ethereum connector (`fromAddressSeed`, path m/44'/60'/<worker>'/0/0).
CALIPER_VECTORS = [
    (
        "0x625c876b12ee5de00f848e4ff2644280cf4420b8",
        "0x19f6c7e282e9947e39666a7bc31d61617ee24b2fcbbfc255caa3782080e258f1",
    ),
    (
        "0x6c8b51832c5ff5d14d70c215e825ea38d3490478",
        "0x9bb4b11985b8763a6628e54616cb3bf8ba8a3078d13d7a370e9162710978750c",
    ),
    (
        "0xe877993fcb99db7728cfd2bf51d04021e0bbea29",
        "0x35e2a9716a7f048c043dd7e4df16dae02ac05c41b9ee441aec510d4bc7dec281",
    ),
]


def test_the_demo_seed_is_the_one_the_vectors_were_printed_for() -> None:
    assert PERF_SEED == "besu-with-firefly perf demo seed"


def test_workers_0_1_2_match_what_caliper_derives() -> None:
    wallets = derive_wallets(3)
    assert [(w.address, w.private_key) for w in wallets] == CALIPER_VECTORS


def test_names_are_numbered_from_one_and_every_address_matches_its_key() -> None:
    wallets = derive_wallets(12)
    assert [w.name for w in wallets][:3] == ["perf-001", "perf-002", "perf-003"]
    assert wallets[-1].name == "perf-012"
    for wallet in wallets:
        verify_wallet(wallet)


def test_the_same_seed_gives_the_same_wallets_and_a_larger_count_extends_them() -> None:
    assert derive_wallets(5) == derive_wallets(5)
    assert derive_wallets(8)[:5] == derive_wallets(5)


def test_another_seed_gives_other_wallets() -> None:
    assert derive_wallets(1, seed="another seed")[0].address != derive_wallets(1)[0].address


@pytest.mark.parametrize("count", [0, -1, 1000])
def test_a_count_outside_1_to_999_is_refused(count: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 999"):
        derive_wallets(count)


def test_the_javascript_side_uses_the_same_seed() -> None:
    from pathlib import Path

    params = Path(__file__).resolve().parents[3] / "perf" / "lib" / "params.js"
    assert f"DEFAULT_SEED = '{PERF_SEED}'" in params.read_text(encoding="utf-8")


def test_a_benchmark_gets_twice_as_many_wallets_the_first_half_for_the_chain_layer() -> None:
    wallets = benchmark_wallets(3)
    assert [w.name for w in wallets] == [f"perf-00{i}" for i in range(1, 7)]
    assert wallets == derive_wallets(6)
    assert len({w.address for w in wallets}) == 6


def test_more_workers_than_half_the_wallet_limit_are_refused() -> None:
    with pytest.raises(ValueError, match="between 1 and 999"):
        benchmark_wallets(500)
