import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from src.adapters.ff_cli import main
from src.core.firefly.errors import FireflyError
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
