from pathlib import Path

import pytest

from src.adapters.docker_stack import StackError
from src.adapters.stack_cli import main
from src.core.network.health import ContainerState
from tests.support.besu_fake import fake_cert_maker, fake_generator


def run(args: list[str], seed: int = 1) -> int:
    return main(args, generator=fake_generator(seed=seed), cert_maker=fake_cert_maker())


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
        self.resets = 0

    def up(self, wait_timeout: float) -> list[ContainerState]:
        self.timeouts.append(wait_timeout)
        if self.error:
            raise StackError(self.error)
        return [ContainerState("besu-validator-1", "running", "healthy")]

    def reset(self) -> list[str]:
        self.resets += 1
        if self.error:
            raise StackError(self.error)
        return ["besu-validator-1", "besu-rpc-anson"]


def test_up_prints_each_service_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    stack = FakeStack()
    assert main(["up", "--timeout", "30"], stack=stack) == 0
    assert stack.timeouts == [30.0]
    out = capsys.readouterr().out
    assert "besu-validator-1" in out and "healthy" in out


def test_up_failure_exits_one_with_the_reason(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["up"], stack=FakeStack(error="besu-validator-2 is starting")) == 1
    assert "besu-validator-2 is starting" in capsys.readouterr().err


def test_reset_prints_what_it_removed_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    stack = FakeStack()
    assert main(["reset"], stack=stack) == 0
    assert stack.resets == 1
    out = capsys.readouterr().out
    assert "besu-validator-1" in out and "besu-rpc-anson" in out


def test_reset_with_nothing_to_remove_says_so(capsys: pytest.CaptureFixture[str]) -> None:
    class Empty(FakeStack):
        def reset(self) -> list[str]:
            return []

    assert main(["reset"], stack=Empty()) == 0
    assert "nothing to remove" in capsys.readouterr().out


def test_reset_exits_one_when_docker_is_not_reachable(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["reset"], stack=FakeStack(error="docker is not reachable")) == 1
    assert "docker is not reachable" in capsys.readouterr().err


def test_up_waits_up_to_five_minutes_by_default() -> None:
    stack = FakeStack()
    assert main(["up"], stack=stack) == 0
    assert stack.timeouts == [300.0]


def test_deploy_runs_the_deployer_and_exits_zero(tmp_path: Path) -> None:
    seen: list[Path] = []

    def deployer(network_dir: Path) -> dict[str, str]:
        seen.append(network_dir)
        return {"id-factory": "0x" + "11" * 20}

    assert main(["deploy", "--network-dir", str(tmp_path)], deployer=deployer) == 0
    assert seen == [tmp_path]


def test_deploy_failure_exits_one_and_names_the_step(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from src.adapters.trex_deploy import DeployStepError

    def deployer(_network_dir: Path) -> dict[str, str]:
        raise DeployStepError("trex-factory", "HTTP 500: boom")

    assert main(["deploy", "--network-dir", str(tmp_path)], deployer=deployer) == 1
    assert "trex-factory: HTTP 500: boom" in capsys.readouterr().err


def test_deploy_without_the_npm_packages_exits_one_with_the_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from src.adapters.trex_artifacts import ArtifactsMissingError

    def deployer(_network_dir: Path) -> dict[str, str]:
        raise ArtifactsMissingError("run `npm ci` in contracts/")

    assert main(["deploy", "--network-dir", str(tmp_path)], deployer=deployer) == 1
    assert "npm ci" in capsys.readouterr().err


def test_onboard_runs_the_onboarder_and_exits_zero(tmp_path: Path) -> None:
    seen: list[Path] = []

    def onboarder(network_dir: Path) -> None:
        seen.append(network_dir)

    assert main(["onboard", "--network-dir", str(tmp_path)], onboarder=onboarder) == 0
    assert seen == [tmp_path]


def test_onboard_failure_exits_one_with_the_reason(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from src.adapters.trex_deploy import DeployStepError

    def onboarder(_network_dir: Path) -> None:
        raise DeployStepError("anson", "HTTP 500: boom")

    assert main(["onboard", "--network-dir", str(tmp_path)], onboarder=onboarder) == 1
    assert "anson: HTTP 500: boom" in capsys.readouterr().err


def test_reset_also_removes_a_stale_deployed_addresses_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    addresses = tmp_path / "deployed-addresses.json"
    addresses.write_text("{}", encoding="utf-8")
    assert main(["reset"], stack=FakeStack(), addresses_file=addresses) == 0
    assert not addresses.exists()
    assert "deployed-addresses.json" in capsys.readouterr().out


def test_reset_without_a_deployed_addresses_file_is_fine(tmp_path: Path) -> None:
    addresses = tmp_path / "deployed-addresses.json"
    assert main(["reset"], stack=FakeStack(), addresses_file=addresses) == 0


def test_a_failed_reset_leaves_the_deployed_addresses_file_alone(tmp_path: Path) -> None:
    addresses = tmp_path / "deployed-addresses.json"
    addresses.write_text("{}", encoding="utf-8")
    stack = FakeStack(error="docker is not reachable")
    assert main(["reset"], stack=stack, addresses_file=addresses) == 1
    assert addresses.exists()
