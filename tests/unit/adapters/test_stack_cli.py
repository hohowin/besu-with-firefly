from pathlib import Path

import pytest

from src.adapters.docker_stack import StackError
from src.adapters.stack_cli import main
from src.core.network.health import ContainerState
from tests.support.besu_fake import fake_generator


def run(args: list[str], seed: int = 1) -> int:
    return main(args, generator=fake_generator(seed=seed))


def test_init_creates_the_network_files_and_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(["init", "--network-dir", str(tmp_path)]) == 0
    assert (tmp_path / "genesis.json").is_file()
    assert "validator-1" in capsys.readouterr().out


def test_second_init_exits_one_and_tells_the_user_about_force(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(["init", "--network-dir", str(tmp_path)])
    capsys.readouterr()
    assert run(["init", "--network-dir", str(tmp_path)], seed=2) == 1
    assert "--force" in capsys.readouterr().err


def test_init_force_regenerates(tmp_path: Path) -> None:
    run(["init", "--network-dir", str(tmp_path)])
    before = (tmp_path / "static-nodes.json").read_bytes()
    assert run(["init", "--network-dir", str(tmp_path), "--force"], seed=2) == 0
    assert (tmp_path / "static-nodes.json").read_bytes() != before


def test_a_generation_failure_exits_one_with_a_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["init", "--network-dir", str(tmp_path)],
        generator=fake_generator(omit_from_extra_data=True),
    )
    assert code == 1
    assert "extraData" in capsys.readouterr().err


def test_no_command_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_unknown_command_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["bogus"])
    assert excinfo.value.code == 2


class FakeStack:
    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.timeouts: list[float] = []

    def up(self, wait_timeout: float) -> list[ContainerState]:
        self.timeouts.append(wait_timeout)
        if self.error:
            raise StackError(self.error)
        return [ContainerState("besu-validator-1", "running", "healthy")]


def test_up_prints_each_service_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    stack = FakeStack()
    assert main(["up", "--timeout", "30"], stack=stack) == 0
    assert stack.timeouts == [30.0]
    out = capsys.readouterr().out
    assert "besu-validator-1" in out and "healthy" in out


def test_up_failure_exits_one_with_the_reason(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["up"], stack=FakeStack(error="besu-validator-2 is starting")) == 1
    assert "besu-validator-2 is starting" in capsys.readouterr().err
