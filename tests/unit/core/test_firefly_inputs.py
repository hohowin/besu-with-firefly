import pytest

from src.core.firefly.inputs import InputError, parse_inputs, resolve_identity

WALLETS = {"anson": "0x" + "a1" * 20, "admin": "0x" + "ad" * 20}


def test_pairs_become_a_mapping_and_values_stay_text() -> None:
    assert parse_inputs(["_amount=25", "label=a=b"], WALLETS) == {"_amount": "25", "label": "a=b"}


def test_an_at_name_becomes_that_wallets_address() -> None:
    assert parse_inputs(["_to=@anson"], WALLETS) == {"_to": WALLETS["anson"]}


def test_an_unknown_wallet_name_is_refused_and_the_known_ones_are_listed() -> None:
    with pytest.raises(InputError, match="anson, admin"):
        parse_inputs(["_to=@nobody"], WALLETS)


@pytest.mark.parametrize("pair", ["novalue", "=5", " =5"])
def test_a_pair_without_a_name_or_equals_sign_is_refused(pair: str) -> None:
    with pytest.raises(InputError):
        parse_inputs([pair], WALLETS)


def test_the_same_name_twice_is_refused() -> None:
    with pytest.raises(InputError, match="twice"):
        parse_inputs(["a=1", "a=2"], WALLETS)


@pytest.mark.parametrize("value", ["0xZZ", "0x123", "0x"])
def test_a_malformed_hex_value_is_refused(value: str) -> None:
    with pytest.raises(InputError, match="hex"):
        parse_inputs([f"_to={value}"], WALLETS)


def test_a_well_formed_address_passes_unchanged() -> None:
    address = "0x" + "Ab" * 20
    assert parse_inputs([f"_to={address}"], WALLETS) == {"_to": address}


def test_resolve_identity_gives_the_address_and_refuses_an_unknown_name() -> None:
    assert resolve_identity("anson", WALLETS) == WALLETS["anson"]
    with pytest.raises(InputError, match="no wallet called 'bob'"):
        resolve_identity("bob", WALLETS)
