"""What a write came to (pure): the one place that decides whether it may be called a success.

Only a `Succeeded` operation is a success. A timeout, a pending operation and a status this code
does not know are all `Pending` (unknown): the write may still land, so nothing is reported as done.
"""

from dataclasses import dataclass

from src.core.firefly.errors import (
    FireflyError,
    OperationFailed,
    OperationTimeout,
    Reverted,
    WriteUnconfirmed,
)
from src.core.firefly.operations import Operation, revert_reason


@dataclass(frozen=True)
class Succeeded:
    operation: Operation


@dataclass(frozen=True)
class Failed:
    error: str | None
    operation_id: str | None


@dataclass(frozen=True)
class ComplianceRevert:
    reason: str


@dataclass(frozen=True)
class Pending:
    operation_id: str | None
    transaction_id: str | None
    status: str


Outcome = Succeeded | Failed | ComplianceRevert | Pending


def classify_operation(operation: Operation) -> Outcome:
    if operation.succeeded:
        return Succeeded(operation)
    if operation.failed:
        return _failure(operation.error, operation.id)
    return Pending(operation.id, operation.tx, operation.status)


def classify_error(error: FireflyError) -> Outcome:
    if isinstance(error, Reverted):
        return ComplianceRevert(error.reason)
    if isinstance(error, OperationFailed):
        return _failure(error.error, error.operation_id)
    if isinstance(error, OperationTimeout):
        return Pending(error.operation_id, None, error.status)
    if isinstance(error, WriteUnconfirmed):
        return Pending(error.operation_id, None, "unknown")
    return Failed(str(error), None)


def _failure(error: str | None, operation_id: str) -> Failed | ComplianceRevert:
    reason = revert_reason(error) if error else None
    return ComplianceRevert(reason) if reason is not None else Failed(error, operation_id)
