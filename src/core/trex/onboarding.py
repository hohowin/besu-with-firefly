"""Onboarding decisions (pure): what is still missing for an account, given what is on chain.

Every write waits for a block, and a repeated one can revert, so each step is sent only when the
state says it is missing (skip-if-already-true).
"""

from dataclasses import dataclass

# Demo wallets that become investors. Admin stays unregistered (it is the unverified recipient
# in the compliance-rejection test).
ONBOARD_ACCOUNTS = ("anson", "beatrice")
COUNTRY = 124  # ISO 3166-1 numeric code (Canada); the demo needs some country, any will do

_ZERO = "0x" + "00" * 20


@dataclass(frozen=True)
class AccountState:
    identity: str | None  # the account's OnchainID address, None if it has none
    registered: bool  # whether the IdentityRegistry contains the account


@dataclass(frozen=True)
class CreateIdentity:
    account: str


@dataclass(frozen=True)
class RegisterIdentity:
    account: str


def registration_steps(
    account: str, state: AccountState
) -> list[CreateIdentity | RegisterIdentity]:
    """The steps still needed for `account` to be registered, in order."""
    if state.registered and state.identity is None:
        raise ValueError(f"{account} is registered but has no identity: the state is inconsistent")
    steps: list[CreateIdentity | RegisterIdentity] = []
    if state.identity is None:
        steps.append(CreateIdentity(account))
    if not state.registered:
        steps.append(RegisterIdentity(account))
    return steps


def identity_from_answer(address: str) -> str | None:
    """An address read from the IdFactory: None for the zero address, else lower case."""
    return None if address.lower() == _ZERO else address.lower()
