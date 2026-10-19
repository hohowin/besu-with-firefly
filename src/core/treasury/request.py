"""The funding request and its state machine (pure). Mirrors `FundingRequest.sol`.

`Status` values equal the contract's enum, so a status read from the chain is `Status(value)`.
"""

from dataclasses import dataclass
from enum import Enum, IntEnum

from src.core.treasury.errors import InvalidReason, InvalidTransition

MAX_REASON_LENGTH = 140


class Status(IntEnum):
    NONE = 0
    REQUESTED = 1
    APPROVED = 2
    REJECTED = 3
    SETTLED = 4
    REDEEMED = 5


class Action(Enum):
    CREATE = "create"
    APPROVE = "approve"
    REJECT = "reject"
    SETTLE = "settle"
    REDEEM = "redeem"


_TRANSITIONS: dict[tuple[Status, Action], Status] = {
    (Status.NONE, Action.CREATE): Status.REQUESTED,
    (Status.REQUESTED, Action.APPROVE): Status.APPROVED,
    (Status.REQUESTED, Action.REJECT): Status.REJECTED,
    (Status.APPROVED, Action.SETTLE): Status.SETTLED,
    (Status.SETTLED, Action.REDEEM): Status.REDEEMED,
}


@dataclass(frozen=True)
class Request:
    """A request as read from the chain. Amounts are minor units, the rate is parts per million."""

    id: str
    requester: str
    amount_cad: int
    processing_date: int
    status: Status
    amount_gbp: int = 0
    rate_ppm: int = 0
    approver: str | None = None


def next_status(status: Status, action: Action) -> Status:
    try:
        return _TRANSITIONS[(status, action)]
    except KeyError:
        raise InvalidTransition(
            f"cannot {action.value} a request that is {status.name.lower()}"
        ) from None


def allowed_actions(status: Status) -> set[Action]:
    return {action for (state, action) in _TRANSITIONS if state is status}


def validate_reason(text: str) -> str:
    """The rejection reason, trimmed. Not empty, at most 140 characters."""
    reason = text.strip()
    if not reason:
        raise InvalidReason("a rejection needs a reason")
    if len(reason) > MAX_REASON_LENGTH:
        raise InvalidReason(
            f"the reason is {len(reason)} characters, the limit is {MAX_REASON_LENGTH}"
        )
    return reason
