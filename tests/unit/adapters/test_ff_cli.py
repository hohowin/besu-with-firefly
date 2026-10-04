import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from src.adapters.ff_cli import main
from src.core.firefly.errors import (
    FireflyError,
    OperationFailed,
    OperationTimeout,
    Reverted,
    WriteUnconfirmed,
)
from src.core.firefly.operations import Operation, TxEvent

ANSON = "0x" + "a1" * 20


class FakePort:
    """Records calls. `answers` maps (api, method) to the answer of a query."""

    def __init__(self, answers: Mapping[tuple[str, str], Any] | None = None) -> None:
        self.answers = dict(answers or {})
        self.calls: list[tuple[str, str, Mapping[str, Any]]] = []
        self.error: Exception | None = None
        self.operations: dict[str, Operation] = {}
        self.events: list[TxEvent] = []

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        self.calls.append((api, method, inputs))
        if self.error:
            raise self.error
        return self.answers[(api, method)]

    def api_invoke(self, *args: Any, **kwargs: Any) -> Operation:
        raise AssertionError("no write expected")

    def get_operation(self, operation_id: str) -> Operation:
        self.calls.append(("operation", operation_id, {}))
        if self.error:
            raise self.error
        return self.operations[operation_id]

    def transaction_events(self, transaction_id: str) -> list[TxEvent]:
        self.calls.append(("events", transaction_id, {}))
        return self.events

    def ensure_interface(self, *args: Any, **kwargs: Any) -> str:
        raise AssertionError("not expected")

    def ensure_api(self, *args: Any, **kwargs: Any) -> str:
        raise AssertionError("not expected")


@pytest.fixture
def network_dir(tmp_path: Path) -> Path:
    wallets = {"wallets": [{"name": "anson", "address": ANSON, "privateKey": "0x" + "11" * 32}]}
    (tmp_path / "wallets.json").write_text(json.dumps(wallets), encoding="utf-8")
    return tmp_path


def run(
    capsys: pytest.CaptureFixture[str], port: FakePort, network_dir: Path, *args: str
) -> tuple[int, str, str]:
    code = main(["--network-dir", str(network_dir), *args], port=port)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_query_prints_the_value_and_resolves_the_wallet_name(
    capsys: pytest.CaptureFixture[str], network_dir: Path
) -> None:
    port = FakePort({("coin", "balanceOf"): "1000000000000000000000"})
    code, out, _ = run(
        capsys, port, network_dir, "query", "balanceOf", "--contract", "coin",
        "--input", "_userAddress=@anson",
    )  # fmt: skip
    assert (code, out) == (0, "1000000000000000000000\n")
    assert port.calls == [("coin", "balanceOf", {"_userAddress": ANSON})]


def test_query_json_prints_one_object(
    capsys: pytest.CaptureFixture[str], network_dir: Path
) -> None:
    port = FakePort({("coin", "name"): "Coin"})
    code, out, _ = run(capsys, port, network_dir, "--json", "query", "name", "--contract", "coin")
    assert code == 0
    assert json.loads(out) == {"contract": "coin", "method": "name", "result": "Coin"}


@pytest.mark.parametrize("value", ["@nobody", "0xZZ", "0x123"])
def test_a_bad_input_exits_non_zero_and_sends_nothing(
    capsys: pytest.CaptureFixture[str], network_dir: Path, value: str
) -> None:
    port = FakePort()
    code, out, err = run(
        capsys, port, network_dir, "query", "balanceOf", "--contract", "coin",
        "--input", f"_userAddress={value}",
    )  # fmt: skip
    assert code == 1 and out == "" and err.startswith("error: ")
    assert port.calls == []


def test_firefly_unreachable_is_a_one_line_error_not_a_traceback(
    capsys: pytest.CaptureFixture[str], network_dir: Path
) -> None:
    port = FakePort()
    port.error = FireflyError("POST /x could not reach FireFly: connection refused")
    code, out, err = run(capsys, port, network_dir, "query", "name", "--contract", "coin")
    assert code == 1 and out == ""
    assert err == "error: POST /x could not reach FireFly: connection refused\n"


def test_missing_wallets_file_is_an_error_only_when_a_name_is_needed(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    port = FakePort({("coin", "name"): "Coin"})
    code, out, _ = run(capsys, port, tmp_path, "query", "name", "--contract", "coin")
    assert (code, out) == (0, "Coin\n")
    code, _, err = run(
        capsys, port, tmp_path, "query", "balanceOf", "--contract", "coin", "--input", "a=@anson"
    )
    assert code == 1 and "wallets.json" in err


def test_tx_prints_status_transaction_and_events(
    capsys: pytest.CaptureFixture[str], network_dir: Path
) -> None:
    port = FakePort()
    port.operations["op1"] = Operation(id="op1", status="Succeeded", tx="tx1")
    port.events = [TxEvent(51, "transaction_submitted", "2026-10-04T14:03:40Z", "tx1")]
    code, out, _ = run(capsys, port, network_dir, "tx", "op1")
    assert code == 0
    assert out.splitlines() == [
        "operation  op1",
        "status     Succeeded",
        "tx         tx1",
        "event      51  transaction_submitted  2026-10-04T14:03:40Z",
    ]
    assert port.calls == [("operation", "op1", {}), ("events", "tx1", {})]


def test_tx_of_an_operation_still_pending_says_so_and_never_says_success(
    capsys: pytest.CaptureFixture[str], network_dir: Path
) -> None:
    port = FakePort()
    port.operations["op1"] = Operation(id="op1", status="Pending", tx="tx1")
    code, out, _ = run(capsys, port, network_dir, "tx", "op1")
    assert code == 0 and "status     Pending" in out
    assert "succe" not in out.lower()


def test_tx_shows_the_error_of_a_failed_operation(
    capsys: pytest.CaptureFixture[str], network_dir: Path
) -> None:
    port = FakePort()
    port.operations["op1"] = Operation(id="op1", status="Failed", tx="tx1", error="boom")
    _, out, _ = run(capsys, port, network_dir, "tx", "op1")
    assert "error      boom" in out


def test_tx_json_has_the_operation_and_the_events(
    capsys: pytest.CaptureFixture[str], network_dir: Path
) -> None:
    port = FakePort()
    port.operations["op1"] = Operation(id="op1", status="Succeeded", tx="tx1")
    port.events = [TxEvent(51, "transaction_submitted", "t", None)]
    _, out, _ = run(capsys, port, network_dir, "--json", "tx", "op1")
    assert json.loads(out) == {
        "operation": {"id": "op1", "status": "Succeeded", "tx": "tx1", "error": None},
        "events": [{"sequence": 51, "type": "transaction_submitted", "created": "t",
                    "reference": None}],
    }  # fmt: skip


def test_tx_of_an_unknown_operation_exits_one_with_fireflys_text(
    capsys: pytest.CaptureFixture[str], network_dir: Path
) -> None:
    port = FakePort()
    port.error = FireflyError("HTTP 404: FF10109: Not found")
    code, out, err = run(capsys, port, network_dir, "tx", "nope")
    assert (code, out) == (1, "")
    assert err == "error: HTTP 404: FF10109: Not found\n"


BEATRICE = "0x" + "b2" * 20


class WritePort(FakePort):
    """A port that also takes writes. Balances come from `balances`, by address."""

    def __init__(self, result: Operation | Exception) -> None:
        super().__init__()
        self.result = result
        self.balances = {ANSON: "1000", BEATRICE: "0"}
        self.writes: list[tuple[str, str, Mapping[str, Any], str | None]] = []

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        return self.balances[inputs["_userAddress"]]

    def api_invoke(
        self,
        api: str,
        method: str,
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = 120.0,
    ) -> Operation:
        self.writes.append((api, method, inputs, key))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def two_wallets(tmp_path: Path) -> Path:
    wallets = {
        "wallets": [
            {"name": "anson", "address": ANSON, "privateKey": "0x" + "11" * 32},
            {"name": "beatrice", "address": BEATRICE, "privateKey": "0x" + "22" * 32},
        ]
    }
    (tmp_path / "wallets.json").write_text(json.dumps(wallets), encoding="utf-8")
    return tmp_path


TRANSFER = (
    "invoke", "transfer", "--contract", "coin", "--as", "anson",
    "--input", "_to=@beatrice", "--input", "_amount=25",
)  # fmt: skip


def test_invoke_success_names_the_identity_and_operation_and_shows_balances(
    capsys: pytest.CaptureFixture[str], two_wallets: Path
) -> None:
    port = WritePort(Operation(id="op1", status="Succeeded", tx="tx1"))
    code, out, err = run(capsys, port, two_wallets, *TRANSFER)
    assert code == 0 and err == ""
    assert out.splitlines()[:3] == [
        "sent       transfer as anson",
        "operation  op1",
        "tx         tx1",
    ]
    assert "balance    anson  1000" in out and "balance    beatrice  0" in out
    assert port.writes == [("coin", "transfer", {"_to": BEATRICE, "_amount": "25"}, ANSON)]


def test_invoke_revert_prints_the_reason_and_says_balances_are_unchanged(
    capsys: pytest.CaptureFixture[str], two_wallets: Path
) -> None:
    port = WritePort(Reverted("Transfer not possible", "HTTP 400"))
    code, out, err = run(capsys, port, two_wallets, *TRANSFER)
    assert code == 1
    assert err == "error: refused by the contract: Transfer not possible\n"
    assert "balances unchanged" in out and "sent" not in out


def test_invoke_failed_exits_one_with_fireflys_text(
    capsys: pytest.CaptureFixture[str], two_wallets: Path
) -> None:
    code, _, err = run(capsys, WritePort(OperationFailed("op1", "boom")), two_wallets, *TRANSFER)
    assert code == 1 and err == "error: operation op1 failed: boom\n"


def test_invoke_pending_is_not_success(
    capsys: pytest.CaptureFixture[str], two_wallets: Path
) -> None:
    port = WritePort(Operation(id="op1", status="Pending", tx="tx1"))
    code, out, err = run(capsys, port, two_wallets, *TRANSFER)
    assert code == 3 and "sent" not in out and "op1" in err and "tx1" in err


def test_invoke_unknown_identity_sends_nothing(
    capsys: pytest.CaptureFixture[str], two_wallets: Path
) -> None:
    port = WritePort(Operation(id="op1", status="Succeeded"))
    code, _, err = run(
        capsys, port, two_wallets, "invoke", "transfer", "--contract", "coin", "--as", "bob"
    )
    assert code == 1 and "no wallet called 'bob'" in err and port.writes == []


def test_invoke_json_never_contains_a_key(
    capsys: pytest.CaptureFixture[str], two_wallets: Path
) -> None:
    port = WritePort(Operation(id="op1", status="Succeeded", tx="tx1"))
    _, out, _ = run(capsys, port, two_wallets, "--json", *TRANSFER)
    document = json.loads(out)
    assert document["status"] == "succeeded" and document["operation"] == "op1"
    assert document["as"] == "anson"
    assert "11" * 32 not in out and "privateKey" not in out


@pytest.mark.parametrize(
    ("result", "known"),
    [
        (Operation(id="op1", status="Pending", tx="tx1"), ["op1", "tx1"]),
        (Operation(id="op1", status="Initialized", tx="tx1"), ["op1", "tx1"]),
        (Operation(id="op1", status="SomethingNew", tx="tx1"), ["op1", "tx1"]),
        (Operation(id="op1", status="", tx=None), ["op1"]),
        (OperationTimeout("op1", "Pending", 5.0), ["op1"]),
        (WriteUnconfirmed("sent, no answer", operation_id="op1"), ["op1"]),
        (WriteUnconfirmed("sent, no answer"), []),
    ],
)
def test_cli_never_reports_success_from_pending(
    capsys: pytest.CaptureFixture[str], two_wallets: Path, result: Operation | Exception,
    known: list[str],
) -> None:  # fmt: skip
    code, out, err = run(capsys, WritePort(result), two_wallets, *TRANSFER)
    assert code == 3
    assert not any(word in (out + err).lower() for word in ("success", "succeeded", "sent  "))
    assert "sent" not in out.split() and "error:" not in err
    assert err.startswith("pending: ")
    assert all(identifier in err for identifier in known)


def test_a_pending_write_without_ids_says_it_may_or_may_not_have_been_sent(
    capsys: pytest.CaptureFixture[str], two_wallets: Path
) -> None:
    port = WritePort(WriteUnconfirmed("sent, no answer"))
    _, _, err = run(capsys, port, two_wallets, *TRANSFER)
    assert "may or may not" in err and "besu-ff tx" not in err


def test_invoke_timeout_is_passed_to_the_write(
    capsys: pytest.CaptureFixture[str], two_wallets: Path
) -> None:
    seen: list[float] = []

    class Spy(WritePort):
        def api_invoke(
            self,
            api: str,
            method: str,
            inputs: Mapping[str, Any],
            key: str | None = None,
            idempotency_key: str | None = None,
            timeout: float = 120.0,
        ) -> Operation:
            seen.append(timeout)
            return super().api_invoke(api, method, inputs, key, idempotency_key, timeout)

    port = Spy(Operation(id="op1", status="Succeeded"))
    run(capsys, port, two_wallets, *TRANSFER, "--timeout", "7")
    run(capsys, port, two_wallets, *TRANSFER)
    assert seen == [7.0, 120.0]


def test_a_read_that_cannot_reach_firefly_still_exits_one(
    capsys: pytest.CaptureFixture[str], network_dir: Path
) -> None:
    port = FakePort()
    port.error = FireflyError("POST /x could not reach FireFly: timed out")
    code, _, err = run(capsys, port, network_dir, "query", "name", "--contract", "coin")
    assert code == 1 and err.startswith("error: ")
