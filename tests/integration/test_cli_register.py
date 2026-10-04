"""`besu-ff register` against the live stack."""

import json
from pathlib import Path

import pytest

from src.adapters.ff_cli import main
from src.adapters.trex_artifacts import load_artifact
from src.core.trex.plan import Deploy, build_plan

pytestmark = pytest.mark.integration

NAME = "coin-copy"


def token_abi_file(directory: Path) -> Path:
    artifact = next(
        s.artifact
        for s in build_plan()
        if isinstance(s, Deploy) and s.name == "token-implementation"
    )
    path = directory / "token-abi.json"
    path.write_text(json.dumps(load_artifact(artifact).abi), encoding="utf-8")
    return path


def register(abi: Path, address: str) -> list[str]:
    return ["register", "--name", NAME, "--abi", str(abi), "--address", address]


def test_register_a_second_api_for_the_token_then_use_it(
    deployed: dict[str, str], capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    abi, token = token_abi_file(tmp_path), deployed["token"]
    assert main(register(abi, token)) == 0
    first = capsys.readouterr().out.splitlines()
    assert first[0] in ("registered  coin-copy", "already registered  coin-copy")  # re-run safe

    assert main(register(abi, token)) == 0
    again = capsys.readouterr().out.splitlines()
    assert again[0] == "already registered  coin-copy"
    assert again[1:] == first[1:]  # the same interface and API ids, nothing new

    assert main(["query", "name", "--contract", NAME]) == 0
    assert capsys.readouterr().out == "Coin\n"


def test_the_same_name_for_another_address_is_refused(
    deployed: dict[str, str], capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    abi = token_abi_file(tmp_path)
    assert main(register(abi, deployed["token"])) == 0
    capsys.readouterr()
    assert main(register(abi, "0x" + "00" * 19 + "01")) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: API 'coin-copy' already exists")
