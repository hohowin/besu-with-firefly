"""`besu-ff query` against the live stack."""

import json

import pytest

from src.adapters.ff_cli import main
from src.core.trex.amounts import to_base_units

pytestmark = pytest.mark.integration


def test_query_name_through_the_coin_api(
    deployed: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["query", "name", "--contract", "coin"]) == 0
    assert capsys.readouterr().out == "Coin\n"


def test_query_balance_of_a_wallet_name_matches_the_chain(
    deployed: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["--json", "query", "balanceOf", "--contract", "coin", "--input", "_userAddress=@anson"]
    )
    result = json.loads(capsys.readouterr().out)
    assert code == 0
    assert result["contract"] == "coin" and result["method"] == "balanceOf"
    # Anson holds 1000 COIN minus whatever he has sent since, so only the range is fixed.
    assert 0 < int(result["result"]) <= to_base_units(1000)


def test_firefly_unreachable_exits_one_without_a_traceback(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import src.adapters.ff_cli as cli
    from src.adapters.firefly import FireflyClient, http_transport

    monkeypatch.setattr(
        cli, "http_transport", lambda: http_transport("http://localhost:9", timeout=2.0)
    )
    monkeypatch.setattr(
        cli, "FireflyClient", lambda transport: FireflyClient(transport, sleep=lambda _s: None)
    )
    assert main(["query", "name", "--contract", "coin"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ")
    assert "Traceback" not in captured.err
