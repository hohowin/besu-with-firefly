import ast
from pathlib import Path

import pytest

from src.adapters.firefly import FireflyClient
from src.core.firefly.errors import (
    FireflyError,
    OperationFailed,
    OperationTimeout,
    Reverted,
)
from src.core.firefly.operations import Operation
from src.core.firefly.outcome import (
    ComplianceRevert,
    Failed,
    Pending,
    Succeeded,
    classify_error,
    classify_operation,
)
from src.core.firefly.port import FireflyPort


def test_a_succeeded_operation_is_the_only_success() -> None:
    operation = Operation(id="op1", status="Succeeded", tx="tx1")
    assert classify_operation(operation) == Succeeded(operation)


@pytest.mark.parametrize("status", ["Pending", "Initialized", "Retry", "", "Whatever", "succeeded"])
def test_any_other_status_is_pending_and_keeps_the_ids(status: str) -> None:
    outcome = classify_operation(Operation(id="op1", status=status, tx="tx1"))
    assert outcome == Pending(operation_id="op1", transaction_id="tx1", status=status)


def test_a_failed_operation_carries_firefly_error_text() -> None:
    outcome = classify_operation(Operation(id="op1", status="Failed", tx="tx1", error="boom"))
    assert outcome == Failed(error="boom", operation_id="op1")


def test_a_failed_operation_with_a_revert_is_a_compliance_revert() -> None:
    error = 'FF23021: EVM reverted: Error("Transfer not possible")'
    outcome = classify_operation(Operation(id="op1", status="Failed", error=error))
    assert outcome == ComplianceRevert(reason="Transfer not possible")


def test_a_revert_error_is_a_compliance_revert_with_the_contracts_reason() -> None:
    outcome = classify_error(Reverted("Transfer not possible", "HTTP 400: ..."))
    assert outcome == ComplianceRevert(reason="Transfer not possible")


def test_an_operation_failed_error_is_failed() -> None:
    assert classify_error(OperationFailed("op1", "boom")) == Failed(
        error="boom", operation_id="op1"
    )


def test_a_timeout_is_pending_never_failed_or_success() -> None:
    outcome = classify_error(OperationTimeout("op1", "Pending", 5.0))
    assert outcome == Pending(operation_id="op1", transaction_id=None, status="Pending")


def test_any_other_firefly_error_is_failed() -> None:
    assert classify_error(FireflyError("HTTP 500: x")) == Failed(
        error="HTTP 500: x", operation_id=None
    )


def conforms(client: FireflyClient) -> FireflyPort:
    return client  # mypy fails here if the client stops implementing the port


def test_core_has_no_print_input_or_network_call() -> None:
    banned_calls = {"print", "input"}
    banned_modules = {"urllib", "http", "socket", "requests", "httpx", "subprocess"}
    core = Path(__file__).resolve().parents[3] / "src" / "core"
    problems: list[str] = []
    for path in core.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in banned_calls
            ):
                problems.append(f"{path.name}: {node.func.id}()")
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            problems += [
                f"{path.name}: import {n}" for n in names if n.split(".")[0] in banned_modules
            ]
    assert problems == []
