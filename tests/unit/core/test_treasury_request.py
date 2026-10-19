import itertools

import pytest

from src.core.treasury.errors import InvalidReason, InvalidTransition
from src.core.treasury.request import (
    MAX_REASON_LENGTH,
    Action,
    Status,
    allowed_actions,
    next_status,
    validate_reason,
)

LEGAL = {
    (Status.NONE, Action.CREATE): Status.REQUESTED,
    (Status.REQUESTED, Action.APPROVE): Status.APPROVED,
    (Status.REQUESTED, Action.REJECT): Status.REJECTED,
    (Status.APPROVED, Action.SETTLE): Status.SETTLED,
    (Status.SETTLED, Action.REDEEM): Status.REDEEMED,
}


@pytest.mark.parametrize(("status", "action"), list(itertools.product(Status, Action)))
def test_only_the_five_legal_transitions_are_allowed(status: Status, action: Action) -> None:
    if (status, action) in LEGAL:
        assert next_status(status, action) is LEGAL[(status, action)]
    else:
        with pytest.raises(InvalidTransition):
            next_status(status, action)


def test_status_values_match_the_contract_enum() -> None:
    assert [s.value for s in Status] == [0, 1, 2, 3, 4, 5]
    assert Status(2) is Status.APPROVED


def test_allowed_actions() -> None:
    assert allowed_actions(Status.REQUESTED) == {Action.APPROVE, Action.REJECT}
    assert allowed_actions(Status.REDEEMED) == set()


def test_reason_rules() -> None:
    assert validate_reason("  too large  ") == "too large"
    assert validate_reason("x" * MAX_REASON_LENGTH) == "x" * MAX_REASON_LENGTH
    with pytest.raises(InvalidReason):
        validate_reason("x" * (MAX_REASON_LENGTH + 1))
    with pytest.raises(InvalidReason):
        validate_reason("   ")
