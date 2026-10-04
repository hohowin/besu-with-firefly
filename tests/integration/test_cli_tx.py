"""`besu-ff tx` against the live stack."""

import pytest

from src.adapters.ff_cli import main
from tests.support.firefly import ff_get

pytestmark = pytest.mark.integration

NS = "/api/v1/namespaces/default"


def test_tx_of_a_succeeded_write_shows_status_transaction_and_events(
    deployed: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    operation = ff_get(f"{NS}/operations?type=blockchain_invoke&status=Succeeded&limit=1")[0]
    assert main(["tx", operation["id"]]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[:3] == [
        f"operation  {operation['id']}",
        "status     Succeeded",
        f"tx         {operation['tx']}",
    ]
    event_types = [line.split()[2] for line in lines if line.startswith("event ")]
    assert event_types == ["transaction_submitted", "blockchain_invoke_op_succeeded"]


def test_tx_of_an_unknown_id_exits_one_with_fireflys_not_found(
    deployed: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["tx", "00000000-0000-0000-0000-000000000000"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "404" in captured.err and "Traceback" not in captured.err
