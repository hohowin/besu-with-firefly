from pathlib import Path

import pytest

from src.adapters.docker_stack import StackError
from src.adapters.stack_cli import main
from src.core.network.health import ContainerState
from tests.support.besu_fake import fake_cert_maker, fake_generator


@pytest.fixture(autouse=True)
def isolated_paladin_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`up` seeds and `reset` removes the Paladin runtime folder: never touch the real ones."""
    from src.adapters import stack_cli
    from src.adapters.paladin_files import write_paladin_files

    source = tmp_path / "_paladin"
    write_paladin_files(source, fake_cert_maker())
    monkeypatch.setattr(stack_cli, "deploy_paladin_phase", lambda: None)  # never the live nodes
    monkeypatch.setattr(stack_cli, "PALADIN_SOURCE", source)
    monkeypatch.setattr(stack_cli, "PALADIN_RUNTIME", tmp_path / "_paladin-runtime")


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


class RecordingStack(FakeStack):
    """Remembers whether the Paladin runtime folder existed when `up` was called."""

    def __init__(self, runtime: Path) -> None:
        super().__init__()
        self.runtime = runtime
        self.runtime_existed_at_up: bool | None = None

    def up(self, wait_timeout: float) -> list[ContainerState]:
        self.runtime_existed_at_up = (self.runtime / "node1" / "pldconf.paladin.yaml").is_file()
        return super().up(wait_timeout)


def test_up_seeds_the_paladin_runtime_config_before_starting_the_containers(
    tmp_path: Path,
) -> None:
    from src.adapters.paladin_files import write_paladin_files

    source, runtime = tmp_path / "paladin", tmp_path / "paladin-runtime"
    write_paladin_files(source, fake_cert_maker())
    stack = RecordingStack(runtime)
    assert main(["up"], stack=stack, paladin_source=source, paladin_runtime=runtime) == 0
    assert stack.runtime_existed_at_up is True


def test_up_without_the_generated_paladin_material_exits_one_and_says_to_run_init(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        ["up"],
        stack=FakeStack(),
        paladin_source=tmp_path / "missing",
        paladin_runtime=tmp_path / "paladin-runtime",
    )
    assert code == 1
    assert "stack.py init" in capsys.readouterr().err


def test_reset_removes_the_paladin_runtime_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runtime = tmp_path / "paladin-runtime"
    (runtime / "node1").mkdir(parents=True)
    (runtime / "node1" / "pldconf.paladin.yaml").write_text("x", encoding="utf-8")
    code = main(
        ["reset"],
        stack=FakeStack(),
        addresses_file=tmp_path / "a.json",
        paladin_runtime=runtime,
    )
    assert code == 0
    assert not runtime.exists()
    assert "paladin-runtime" in capsys.readouterr().out


def test_a_failed_reset_keeps_the_paladin_runtime_folder(tmp_path: Path) -> None:
    runtime = tmp_path / "paladin-runtime"
    runtime.mkdir()
    code = main(
        ["reset"],
        stack=FakeStack(error="docker is not reachable"),
        addresses_file=tmp_path / "a.json",
        paladin_runtime=runtime,
    )
    assert code == 1
    assert runtime.exists()


def test_deploy_runs_the_paladin_phase_after_the_trex_phase(tmp_path: Path) -> None:
    order: list[str] = []

    def deployer(_network_dir: Path) -> dict[str, str]:
        order.append("trex")
        return {}

    def paladin() -> None:
        order.append("paladin")

    assert (
        main(
            ["deploy", "--network-dir", str(tmp_path)], deployer=deployer, paladin_deployer=paladin
        )
        == 0
    )
    assert order == ["trex", "paladin"]


def test_a_failed_trex_phase_skips_the_paladin_phase(tmp_path: Path) -> None:
    from src.adapters.trex_deploy import DeployStepError

    ran: list[str] = []

    def deployer(_network_dir: Path) -> dict[str, str]:
        raise DeployStepError("trex-factory", "boom")

    code = main(
        ["deploy", "--network-dir", str(tmp_path)],
        deployer=deployer,
        paladin_deployer=lambda: ran.append("paladin"),
    )
    assert code == 1 and ran == []


def test_a_failed_paladin_phase_exits_one_and_names_the_step(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from src.adapters.paladin_deploy import PaladinBootstrapError

    def paladin() -> None:
        raise PaladinBootstrapError("noto_factory", "reverted")

    code = main(
        ["deploy", "--network-dir", str(tmp_path)],
        deployer=lambda _d: {},
        paladin_deployer=paladin,
    )
    assert code == 1
    assert "noto_factory: reverted" in capsys.readouterr().err


def test_noto_demo_runs_the_demo_and_exits_zero() -> None:
    calls: list[str] = []

    def demo() -> str:
        calls.append("ran")
        return "0xtoken"

    assert main(["noto-demo"], demo_runner=demo) == 0
    assert calls == ["ran"]


def test_noto_demo_on_an_undeployed_stack_exits_one_and_says_to_deploy(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from src.adapters.paladin_demo import NotDeployed

    def demo() -> str:
        raise NotDeployed("the Paladin contracts are not deployed, run `stack.py deploy` first")

    assert main(["noto-demo"], demo_runner=demo) == 1
    assert "run `stack.py deploy` first" in capsys.readouterr().err


def test_noto_demo_that_saw_a_leak_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    from src.adapters.paladin_demo import DemoFailed

    def demo() -> str:
        raise DemoFailed("node3: leak, sees [100]")

    assert main(["noto-demo"], demo_runner=demo) == 1
    assert "leak" in capsys.readouterr().err
