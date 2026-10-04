import pytest

from src.core.perf.setup import coins_missing
from src.core.trex.amounts import to_base_units


@pytest.mark.parametrize(
    ("balance", "target", "expected"),
    [
        (0, 100, 100),
        ("0", 100, 100),
        (to_base_units(40), 100, 60),
        (to_base_units(100), 100, 0),
        (to_base_units(250), 100, 0),
    ],
)
def test_the_coins_missing_are_what_it_takes_to_reach_the_target(
    balance: int | str, target: int, expected: int
) -> None:
    assert coins_missing(balance, target) == to_base_units(expected)


def test_a_balance_that_is_not_whole_coins_still_gets_topped_up_exactly() -> None:
    assert coins_missing(to_base_units(1) // 2, 1) == to_base_units(1) // 2


def test_a_negative_target_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        coins_missing(0, -1)
