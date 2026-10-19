import pytest

from src.core.firefly.operations import Operation
from src.core.firefly.outcome import ComplianceRevert, Failed, Pending, Succeeded
from src.core.treasury.messages import REVERT_MESSAGES, describe, explain_revert
from src.core.treasury.request import Action

CONTRACT_REVERTS = [
    "NotRequester",
    "Exists",
    "BadAmount",
    "BadDate",
    "NotApprover",
    "SelfApproval",
    "BadState",
    "ReasonTooLong",
    "NotTreasury",
    "BadRate",
    "NotBeneficiary",
]


@pytest.mark.parametrize("code", CONTRACT_REVERTS)
def test_every_contract_revert_has_a_readable_message(code: str) -> None:
    message = explain_revert(code)
    assert message != code
    assert message in REVERT_MESSAGES.values()


def test_an_unknown_revert_reason_is_shown_as_it_is() -> None:
    assert explain_revert("something new") == "something new"


def _operation(status: str) -> Operation:
    return Operation(id="op1", status=status, tx="tx1")


def test_only_a_succeeded_operation_is_done() -> None:
    shown = describe(Succeeded(_operation("Succeeded")), Action.APPROVE)
    assert shown.kind == "done"
    assert shown.operation_id == "op1"
    assert "approved" in shown.message.lower()


def test_pending_is_never_reported_as_done_and_keeps_the_ids() -> None:
    shown = describe(Pending("op1", "tx1", "Pending"), Action.SETTLE)
    assert shown.kind == "pending"
    assert shown.operation_id == "op1"
    assert "op1" in shown.message


def test_a_revert_is_explained() -> None:
    shown = describe(ComplianceRevert("SelfApproval"), Action.APPROVE)
    assert shown.kind == "reverted"
    assert shown.code == "SelfApproval"
    assert shown.message == REVERT_MESSAGES["SelfApproval"]


def test_a_failure_carries_the_error_text() -> None:
    shown = describe(Failed("connector down", "op9"), Action.CREATE)
    assert shown.kind == "failed"
    assert "connector down" in shown.message
    assert shown.operation_id == "op9"


def test_a_failure_with_no_text_still_says_something() -> None:
    assert describe(Failed(None, None), Action.REDEEM).message
