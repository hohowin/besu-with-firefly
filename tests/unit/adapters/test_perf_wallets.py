import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from src.adapters.docker_stack import StackError
from src.adapters.perf_wallets import load_perf_wallets, signer_accounts
from src.core.firefly.keystore import DEMO_PASSWORD
from src.core.network.wallets import Wallet
from src.core.perf.wallets import derive_wallets

WALLETS = derive_wallets(3)


class FakeSigner:
    """A signer that lists what it was started with, and re-reads the folder when restarted."""

    def __init__(self, signer_data: Path) -> None:
        self.signer_data = signer_data
        self.listed: list[str] = []
        self.restarts = 0

    def restart(self, container: str) -> None:
        assert container == "firefly-signer"
        self.restarts += 1
        folder = self.signer_data / "keystore"
        self.listed = sorted("0x" + p.name for p in folder.glob("*") if "." not in p.name)

    def accounts(self) -> list[str]:
        return list(self.listed)


def load(signer_data: Path, signer: FakeSigner, wallets: Sequence[Wallet] = WALLETS) -> list[str]:
    ticks = iter(range(10_000))
    return load_perf_wallets(
        wallets,
        signer_data,
        restart=signer.restart,
        accounts=signer.accounts,
        sleep=lambda _s: None,
        clock=lambda: float(next(ticks)),
    )


def test_new_wallets_are_written_as_keystores_and_the_signer_is_restarted(tmp_path: Path) -> None:
    signer = FakeSigner(tmp_path)
    written = load(tmp_path, signer)
    assert written == ["perf-001", "perf-002", "perf-003"]
    for wallet in WALLETS:
        stem = wallet.address.removeprefix("0x")
        keystore = json.loads((tmp_path / "keystore" / stem).read_text(encoding="utf-8"))
        assert keystore["address"].lower() == stem
        toml = (tmp_path / "keystore" / f"{stem}.toml").read_text(encoding="utf-8")
        assert f'key-file = "/data/keystore/{stem}"' in toml
    assert (tmp_path / "password").read_text(encoding="utf-8") == DEMO_PASSWORD
    assert signer.restarts == 1


def test_running_again_writes_nothing_and_restarts_nothing(tmp_path: Path) -> None:
    signer = FakeSigner(tmp_path)
    load(tmp_path, signer)
    before = {p.name: p.read_bytes() for p in (tmp_path / "keystore").iterdir()}
    assert load(tmp_path, signer) == []
    assert {p.name: p.read_bytes() for p in (tmp_path / "keystore").iterdir()} == before
    assert signer.restarts == 1


def test_a_smaller_count_later_removes_nothing(tmp_path: Path) -> None:
    signer = FakeSigner(tmp_path)
    load(tmp_path, signer)
    assert load(tmp_path, signer, WALLETS[:1]) == []
    assert len(list((tmp_path / "keystore").glob("*.toml"))) == 3


def test_a_larger_count_later_writes_only_the_new_wallets(tmp_path: Path) -> None:
    signer = FakeSigner(tmp_path)
    load(tmp_path, signer, WALLETS[:2])
    assert load(tmp_path, signer, WALLETS) == ["perf-003"]
    assert signer.restarts == 2


def test_files_already_there_but_not_loaded_by_the_signer_restart_it_anyway(
    tmp_path: Path,
) -> None:
    """An earlier run that stopped between writing and restarting leaves exactly this state."""
    load(tmp_path, FakeSigner(tmp_path))
    signer = FakeSigner(tmp_path)  # a signer that does not list them
    assert load(tmp_path, signer) == []
    assert signer.restarts == 1


def test_a_signer_that_never_lists_the_wallets_is_an_error(tmp_path: Path) -> None:
    class Deaf(FakeSigner):
        def restart(self, container: str) -> None:
            self.restarts += 1

    with pytest.raises(StackError, match="perf-001"):
        load(tmp_path, Deaf(tmp_path))


def test_signer_accounts_reads_eth_accounts_through_docker_exec() -> None:
    seen: list[list[str]] = []

    def runner(command: Sequence[str]) -> tuple[int, str, str]:
        seen.append(list(command))
        return 0, '{"jsonrpc":"2.0","id":1,"result":["0xAA","0xbb"]}', ""

    assert signer_accounts(runner) == ["0xaa", "0xbb"]
    assert seen[0][:3] == ["docker", "exec", "firefly-signer"]
    assert "eth_accounts" in " ".join(seen[0])


def test_signer_accounts_fails_with_the_command_error() -> None:
    with pytest.raises(StackError, match="not running"):
        signer_accounts(lambda command: (1, "", "container not running"))
