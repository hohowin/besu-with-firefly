import json
import threading
from pathlib import Path

import pytest

from src.adapters.treasury_app import Sweeper, load_fx_file, load_wallet_addresses
from src.core.treasury.errors import InvalidRate

DOC = {"notice": "x", "CADGBP": {"default": "0.580000", "2026-10-18": "0.581200"}}


def test_the_rate_file_is_read_each_time(tmp_path: Path) -> None:
    path = tmp_path / "fx-rates.json"
    path.write_text(json.dumps(DOC), encoding="utf-8")
    assert load_fx_file(path).default == 580000
    path.write_text(json.dumps({"CADGBP": {"default": "0.600000"}}), encoding="utf-8")
    assert load_fx_file(path).default == 600000  # a change needs no restart


@pytest.mark.parametrize("text", ["{not json", "[]", "", '{"CADGBP": {"default": "abc"}}'])
def test_a_bad_rate_file_is_an_invalid_rate_error_naming_the_file(
    tmp_path: Path, text: str
) -> None:
    path = tmp_path / "fx-rates.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(InvalidRate, match="fx-rates.json"):
        load_fx_file(path)


def test_a_missing_rate_file_is_an_invalid_rate_error(tmp_path: Path) -> None:
    with pytest.raises(InvalidRate, match="fx-rates.json"):
        load_fx_file(tmp_path / "fx-rates.json")


def test_wallet_addresses_never_include_a_key(tmp_path: Path) -> None:
    (tmp_path / "wallets.json").write_text(
        json.dumps(
            {
                "wallets": [
                    {"name": "ldn", "address": "0xAbC", "privateKey": "0xsecret"},
                    {"name": "tor", "address": "0xdef", "privateKey": "0xsecret2"},
                ]
            }
        ),
        encoding="utf-8",
    )
    found = load_wallet_addresses(tmp_path)
    assert found == {"ldn": "0xabc", "tor": "0xdef"}
    assert "secret" not in str(found)


def test_the_sweeper_runs_the_sweep_in_the_background() -> None:
    done = threading.Event()

    class FakeService:
        def sweep(self) -> list[object]:
            done.set()
            return []

    sweeper = Sweeper(FakeService(), lambda _entry: None)
    sweeper.trigger()
    assert done.wait(5)


def test_a_failing_sweep_is_logged_and_does_not_kill_the_caller() -> None:
    logged: list[dict[str, object]] = []
    seen = threading.Event()

    class BrokenService:
        def sweep(self) -> list[object]:
            raise RuntimeError("firefly is down")

    def log(entry: dict[str, object]) -> None:
        logged.append(entry)
        seen.set()

    Sweeper(BrokenService(), log).trigger()
    assert seen.wait(5)
    assert logged[0]["outcome"] == "error"
    assert "firefly is down" in str(logged[0]["message"])
