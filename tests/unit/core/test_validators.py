import pytest

from src.core.network.validators import extra_data_lists_all, normalize_address, sort_validators

A = "0x163f625372a80c5d2b79f3ae17bfe3f9266ca975"
B = "0x456c76f7095e3756fb4b230a5f81047101dcba6c"
C = "0xde28c7855d369ce6eabe75409d32c343f0111549"


def test_normalize_address_lowercases_and_adds_the_prefix() -> None:
    assert normalize_address(A.upper().replace("0X", "0x")) == A
    assert normalize_address(A.removeprefix("0x")) == A


@pytest.mark.parametrize("bad", ["", "0x1234", "0x" + "g" * 40, "0x" + "a" * 41])
def test_normalize_address_rejects_anything_but_40_hex_characters(bad: str) -> None:
    with pytest.raises(ValueError, match="40 hex characters"):
        normalize_address(bad)


def test_sort_validators_orders_by_address_and_normalizes() -> None:
    assert sort_validators([C, A.upper().replace("0X", "0x"), B]) == [A, B, C]


def test_sort_validators_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        sort_validators([A, B, A.upper().replace("0X", "0x")])


def test_extra_data_lists_all_finds_every_address_in_any_position() -> None:
    extra = "0x" + "00" * 32 + A.removeprefix("0x") + B.removeprefix("0x") + "c0"
    assert extra_data_lists_all(extra, [A, B])


def test_extra_data_lists_all_fails_when_one_address_is_missing() -> None:
    extra = "0x" + "00" * 32 + A.removeprefix("0x")
    assert not extra_data_lists_all(extra, [A, B])


def test_extra_data_lists_all_is_case_insensitive() -> None:
    extra = "0x" + A.removeprefix("0x").upper()
    assert extra_data_lists_all(extra, [A])
