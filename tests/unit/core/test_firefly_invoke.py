from collections.abc import Mapping
from typing import Any

import pytest

from src.core.firefly.errors import FireflyError, OperationFailed, Reverted
from src.core.firefly.invoke import run_invoke
from src.core.firefly.operations import Operation
from src.core.firefly.outcome import ComplianceRevert, Failed, Pending, Succeeded

SENDER = "0x" + "a1" * 20
RECIPIENT = "0x" + "b2" * 20


class Port:
    def __init__(self, result: Operation | Exception, balances: list[dict[str, str]]) -> None:
        self.result = result
        self.balances = balances  # one snapshot per phase: before, then after
        self.calls: list[str] = []
        self._reads = 0

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        self.calls.append(f"query {method}")
        phase = min(self._reads // 2, len(self.balances) - 1)
        self._reads += 1
        return self.balances[phase][inputs["_userAddress"]]

    def api_invoke(
        self,
        api: str,
        method: str,
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = 120.0,
    ) -> Operation:
        self.calls.append(f"invoke {method}")
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def snapshot(sender: str, recipient: str) -> dict[str, str]:
    return {SENDER: sender, RECIPIENT: recipient}


def transfer(port: Port) -> Any:
    return run_invoke(port, "coin", "transfer", {"_to": RECIPIENT, "_amount": "25"}, SENDER)


def test_a_succeeded_transfer_reports_the_balances_before_and_after() -> None:
    operation = Operation(id="op1", status="Succeeded", tx="tx1")
    port = Port(operation, [snapshot("1000", "0"), snapshot("975", "25")])
    report = transfer(port)
    assert report.outcome == Succeeded(operation)
    assert report.before == snapshot("1000", "0")
    assert report.after == snapshot("975", "25")


def test_balances_are_read_before_the_write_and_after_it() -> None:
    port = Port(Operation(id="op1", status="Succeeded"), [snapshot("1", "0")])
    transfer(port)
    assert port.calls == ["query balanceOf"] * 2 + ["invoke transfer"] + ["query balanceOf"] * 2


def test_a_revert_is_a_compliance_revert_and_the_balances_are_unchanged() -> None:
    port = Port(Reverted("Transfer not possible", "HTTP 400"), [snapshot("1000", "0")])
    report = transfer(port)
    assert report.outcome == ComplianceRevert("Transfer not possible")
    assert report.before == report.after == snapshot("1000", "0")


def test_a_failed_operation_is_failed() -> None:
    port = Port(OperationFailed("op1", "boom"), [snapshot("1", "0")])
    assert transfer(port).outcome == Failed("boom", "op1")


def test_a_write_still_pending_is_pending_not_success() -> None:
    port = Port(Operation(id="op1", status="Pending", tx="tx1"), [snapshot("1", "0")])
    assert transfer(port).outcome == Pending("op1", "tx1", "Pending")


def test_a_method_that_is_not_a_transfer_reads_no_balances() -> None:
    port = Port(Operation(id="op1", status="Succeeded"), [{}])
    report = run_invoke(port, "coin", "unpause", {}, SENDER)
    assert port.calls == ["invoke unpause"]
    assert report.before == report.after == {}


def test_a_failed_balance_read_before_the_write_stops_before_anything_is_sent() -> None:
    class Down(Port):
        def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
            raise FireflyError("could not reach FireFly")

    port = Down(Operation(id="op1", status="Succeeded"), [{}])
    with pytest.raises(FireflyError):
        transfer(port)
    assert port.calls == []


def test_a_failed_balance_read_after_a_success_does_not_hide_the_success() -> None:
    class DownAfter(Port):
        def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
            if "invoke transfer" in self.calls:
                raise FireflyError("gone")
            return super().api_query(api, method, inputs)

    operation = Operation(id="op1", status="Succeeded")
    report = transfer(DownAfter(operation, [snapshot("1", "0")]))
    assert report.outcome == Succeeded(operation)
    assert report.after == {}
