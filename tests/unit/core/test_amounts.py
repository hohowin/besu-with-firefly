import pytest

from src.core.trex.amounts import (
    COIN_UNITS,
    MINT_AMOUNT,
    from_base_units,
    mint_needed,
    to_base_units,
)


def test_a_coin_is_ten_to_the_eighteenth_base_units() -> None:
    assert COIN_UNITS == 10**18
    assert to_base_units(1) == 10**18
    assert to_base_units(25) == 25 * 10**18


def test_base_units_convert_back_to_whole_coins() -> None:
    assert from_base_units(1000 * 10**18) == 1000
    assert from_base_units("975000000000000000000") == 975
    assert from_base_units(0) == 0


def test_an_amount_that_is_not_a_whole_number_of_coins_is_rejected() -> None:
    with pytest.raises(ValueError, match="whole"):
        from_base_units(10**18 + 1)
    with pytest.raises(ValueError, match="negative"):
        to_base_units(-1)


def test_the_initial_supply_is_one_thousand_coins() -> None:
    assert MINT_AMOUNT == 1000


def test_minting_is_needed_until_the_supply_reaches_the_target() -> None:
    assert mint_needed(0) is True
    assert mint_needed(to_base_units(999)) is True
    assert mint_needed(to_base_units(1000)) is False
    assert mint_needed("1000000000000000000000") is False
    # Transfers do not change the supply, so a later run does not mint again.
    assert mint_needed(to_base_units(1000)) is False
