import pytest

from src.core.trex.onboarding import (
    ONBOARD_ACCOUNTS,
    AccountState,
    CreateIdentity,
    RegisterIdentity,
    identity_from_answer,
    registration_steps,
)

IDENTITY = "0x" + "12" * 20


def test_nothing_done_needs_an_identity_and_then_a_registration() -> None:
    assert registration_steps("anson", AccountState(identity=None, registered=False)) == [
        CreateIdentity("anson"),
        RegisterIdentity("anson"),
    ]


def test_an_identity_that_exists_only_needs_registering() -> None:
    assert registration_steps("anson", AccountState(identity=IDENTITY, registered=False)) == [
        RegisterIdentity("anson")
    ]


def test_everything_done_needs_nothing() -> None:
    assert registration_steps("anson", AccountState(identity=IDENTITY, registered=True)) == []


def test_registered_without_an_identity_is_an_inconsistent_state() -> None:
    with pytest.raises(ValueError, match="registered but has no identity"):
        registration_steps("anson", AccountState(identity=None, registered=True))


def test_a_zero_address_answer_means_no_identity() -> None:
    assert identity_from_answer("0x" + "00" * 20) is None
    assert identity_from_answer(IDENTITY.upper().replace("0X", "0x")) == IDENTITY


def test_anson_and_beatrice_are_onboarded_and_admin_is_not() -> None:
    assert ONBOARD_ACCOUNTS == ("anson", "beatrice")
