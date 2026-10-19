"""What the UI says about a write (pure). Only a `Succeeded` operation is "done".

Contract reverts are plain strings (`require(ok, "SelfApproval")`) because FireFly's error text
only carries `Error("...")` reasons; a custom error would arrive as "no reason given".
"""

from dataclasses import dataclass
from typing import Literal

from src.core.firefly.outcome import ComplianceRevert, Failed, Outcome, Pending, Succeeded
from src.core.treasury.request import Action

REVERT_MESSAGES: dict[str, str] = {
    "NotRequester": "This wallet may not create funding requests.",
    "Exists": "A request with this id already exists.",
    "BadAmount": "The amount is zero, above the cap, or converts to less than 0.01.",
    "BadDate": "The processing date is not a valid date.",
    "NotApprover": "This wallet may not approve or reject requests.",
    "SelfApproval": "You cannot approve or reject your own request.",
    "BadState": "The request is not in a state that allows this step.",
    "ReasonTooLong": "The rejection reason is longer than 140 characters.",
    "NotTreasury": "Only the treasury wallet may settle.",
    "BadRate": "The FX rate is outside the range the contract accepts.",
    "NotBeneficiary": "Only the wallet that received the funds may redeem them.",
}

_DONE: dict[Action, str] = {
    Action.CREATE: "Request created.",
    Action.APPROVE: "Request approved, CADC minted to the treasury.",
    Action.REJECT: "Request rejected.",
    Action.SETTLE: "Settled: CADC burned and GBPC minted.",
    Action.REDEEM: "Redeemed: GBPC burned.",
}


@dataclass(frozen=True)
class Display:
    kind: Literal["done", "pending", "reverted", "failed"]
    message: str
    operation_id: str | None = None
    code: str | None = None


def explain_revert(reason: str) -> str:
    return REVERT_MESSAGES.get(reason, reason)


def describe(outcome: Outcome, action: Action) -> Display:
    if isinstance(outcome, Succeeded):
        return Display("done", _DONE[action], outcome.operation.id)
    if isinstance(outcome, ComplianceRevert):
        return Display("reverted", explain_revert(outcome.reason), code=outcome.reason)
    if isinstance(outcome, Pending):
        where = f" (operation {outcome.operation_id})" if outcome.operation_id else ""
        return Display(
            "pending",
            f"Not confirmed yet{where}. Check again before repeating the step.",
            outcome.operation_id,
        )
    assert isinstance(outcome, Failed)
    return Display(
        "failed", outcome.error or "The write failed with no error text.", outcome.operation_id
    )
