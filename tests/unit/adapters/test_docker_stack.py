import json
from collections.abc import Callable, Sequence

import pytest

from src.adapters.docker_stack import DockerStack, StackError

SERVICES = "besu-validator-1\nbesu-validator-2\n"
UP_COMMAND = ["docker", "compose", "up", "-d", "besu-validator-1", "besu-validator-2"]


def ps(*health: str) -> str:
    return "\n".join(
        json.dumps({"Service": f"besu-validator-{i}", "State": "running", "Health": h})
        for i, h in enumerate(health, start=1)
    )


class FakeRunner:
    """Replays canned results for each docker command and records what was run."""

    def __init__(self, ps_outputs: list[str], up_code: int = 0, down_code: int = 0) -> None:
        self.ps_outputs = list(ps_outputs)
        self.up_code = up_code
        self.down_code = down_code
        self.commands: list[list[str]] = []

    def __call__(self, command: Sequence[str]) -> tuple[int, str, str]:
        self.commands.append(list(command))
        if command[:3] == ["docker", "compose", "config"]:
            return 0, SERVICES, ""
        if command[:3] == ["docker", "compose", "up"]:
            return self.up_code, "", "boom" if self.up_code else ""
        if command[:3] == ["docker", "compose", "down"]:
            return self.down_code, "", "daemon not reachable" if self.down_code else ""
        if command[:3] == ["docker", "compose", "ps"]:
            return 0, self.ps_outputs.pop(0) if len(self.ps_outputs) > 1 else self.ps_outputs[0], ""
        raise AssertionError(f"unexpected command {command}")


def make_stack(
    runner: FakeRunner, chain_heights: Callable[[], dict[str, int | None]] | None = None
) -> DockerStack:
    return DockerStack(
        runner=runner,
        sleep=lambda _seconds: None,
        clock=iter(range(1000)).__next__,
        chain_heights=chain_heights,
    )


def test_up_starts_the_stack_and_returns_once_every_service_is_healthy() -> None:
    runner = FakeRunner(
        [ps("starting", "starting"), ps("healthy", "starting"), ps("healthy", "healthy")]
    )
    states = make_stack(runner).up(wait_timeout=100)
    assert [s.service for s in states] == ["besu-validator-1", "besu-validator-2"]
    assert UP_COMMAND in runner.commands


def test_up_names_the_long_running_services_and_leaves_one_shot_jobs_to_their_dependents() -> None:
    """`paladin-seed` and `deployer` run once and exit. `up` must not wait for them to be healthy
    (they never are) and must not start `deployer` (that is `deploy`'s job); `paladin-seed` still
    runs because the Paladin nodes depend on it."""

    class WithJobs(FakeRunner):
        def __call__(self, command: Sequence[str]) -> tuple[int, str, str]:
            if command[:3] == ["docker", "compose", "config"]:
                self.commands.append(list(command))
                return 0, SERVICES + "paladin-seed\ndeployer\n", ""
            return super().__call__(command)

    runner = WithJobs([ps("healthy", "healthy")])
    make_stack(runner).up(wait_timeout=100)
    assert UP_COMMAND in runner.commands


def test_up_times_out_and_names_the_services_that_are_not_healthy() -> None:
    runner = FakeRunner([ps("healthy", "starting")])
    with pytest.raises(StackError, match=r"besu-validator-2.*starting"):
        make_stack(runner).up(wait_timeout=5)


def test_up_reports_a_failing_compose_command() -> None:
    with pytest.raises(StackError, match="boom"):
        make_stack(FakeRunner([ps("healthy", "healthy")], up_code=1)).up(wait_timeout=5)


def test_logs_strip_ansi_colour_codes() -> None:
    def runner(command: Sequence[str]) -> tuple[int, str, str]:
        assert command[:2] == ["docker", "logs"]
        return 0, "\x1b[32mINFO\x1b[0m hello", ""

    assert DockerStack(runner=runner).logs("besu-validator-1") == "INFO hello"


def test_logs_of_a_missing_container_raise_stack_error() -> None:
    def runner(command: Sequence[str]) -> tuple[int, str, str]:
        return 1, "", "No such container"

    with pytest.raises(StackError, match="No such container"):
        DockerStack(runner=runner).logs("nope")


def test_started_at_reads_the_container_start_time() -> None:
    def runner(command: Sequence[str]) -> tuple[int, str, str]:
        assert command[:2] == ["docker", "inspect"] and "besu-validator-1" in command
        return 0, "2026-10-02T13:59:56.628264804Z\n", ""

    assert DockerStack(runner=runner).started_at("besu-validator-1") == (
        "2026-10-02T13:59:56.628264804Z"
    )


def test_published_ports_lists_what_docker_reports() -> None:
    def runner(command: Sequence[str]) -> tuple[int, str, str]:
        assert command[:2] == ["docker", "port"]
        return 0, "8545/tcp -> 0.0.0.0:8545\n", ""

    assert DockerStack(runner=runner).published_ports("besu-rpc-anson") == [
        "8545/tcp -> 0.0.0.0:8545"
    ]


def test_published_ports_is_empty_for_a_container_without_ports() -> None:
    stack = DockerStack(runner=lambda _command: (0, "", ""))
    assert stack.published_ports("besu-validator-1") == []


def test_stop_and_start_run_the_matching_docker_commands() -> None:
    commands: list[list[str]] = []

    def runner(command: Sequence[str]) -> tuple[int, str, str]:
        commands.append(list(command))
        return 0, "", ""

    stack = DockerStack(runner=runner)
    stack.stop("besu-validator-4")
    stack.start("besu-validator-4")
    assert commands == [
        ["docker", "stop", "--time", "10", "besu-validator-4"],
        ["docker", "start", "besu-validator-4"],
    ]


def test_stop_of_a_missing_container_raises_stack_error() -> None:
    stack = DockerStack(runner=lambda _command: (1, "", "No such container: nope"))
    with pytest.raises(StackError, match="No such container"):
        stack.stop("nope")


def test_logs_without_a_tail_return_the_whole_log() -> None:
    seen: list[list[str]] = []

    def runner(command: Sequence[str]) -> tuple[int, str, str]:
        seen.append(list(command))
        return 0, "line", ""

    DockerStack(runner=runner).logs("besu-validator-1")
    assert seen == [["docker", "logs", "besu-validator-1"]]


def test_reset_removes_containers_and_volumes_and_names_what_it_removed() -> None:
    runner = FakeRunner([ps("healthy", "healthy")])
    removed = make_stack(runner).reset()
    assert removed == ["besu-validator-1", "besu-validator-2"]
    assert ["docker", "compose", "ps", "-a", "--format", "json"] in runner.commands
    assert ["docker", "compose", "down", "--volumes", "--remove-orphans"] in runner.commands


def test_reset_of_a_stack_that_is_not_running_removes_nothing() -> None:
    assert make_stack(FakeRunner([""])).reset() == []


def test_reset_reports_a_docker_failure() -> None:
    with pytest.raises(StackError, match="daemon not reachable"):
        make_stack(FakeRunner([ps("healthy")], down_code=1)).reset()


class Heights:
    """A fake chain reader: each call returns the next scripted height per node."""

    def __init__(self, *steps: dict[str, int | None]) -> None:
        self.steps = list(steps)
        self.calls = 0

    def __call__(self) -> dict[str, int | None]:
        self.calls += 1
        return self.steps.pop(0) if len(self.steps) > 1 else self.steps[0]


def test_up_waits_for_the_chain_to_pass_block_zero_after_the_containers_are_healthy() -> None:
    heights = Heights(
        {"besu-rpc-anson": 0, "besu-rpc-beatrice": 0},
        {"besu-rpc-anson": 1, "besu-rpc-beatrice": 0},
        {"besu-rpc-anson": 2, "besu-rpc-beatrice": 1},
    )
    runner = FakeRunner([ps("healthy", "healthy")])
    make_stack(runner, heights).up(wait_timeout=100)
    assert heights.calls == 3


def test_up_fails_when_a_node_never_passes_block_zero_and_names_it() -> None:
    heights = Heights({"besu-rpc-anson": 4, "besu-rpc-beatrice": 0})
    with pytest.raises(StackError, match=r"besu-rpc-beatrice.*block 0"):
        make_stack(FakeRunner([ps("healthy", "healthy")]), heights).up(wait_timeout=5)


def test_up_treats_an_unreachable_node_as_not_ready() -> None:
    heights = Heights({"besu-rpc-anson": None, "besu-rpc-beatrice": 3})
    with pytest.raises(StackError, match=r"besu-rpc-anson.*unreachable"):
        make_stack(FakeRunner([ps("healthy", "healthy")]), heights).up(wait_timeout=5)


def test_a_command_that_runs_too_long_is_reported_as_a_timeout_not_a_traceback() -> None:
    import sys

    from src.adapters.docker_stack import subprocess_runner

    run = subprocess_runner(timeout=0.5)
    code, _out, err = run([sys.executable, "-c", "import time; time.sleep(30)"])
    assert code == 124
    assert "timed out after 0.5s" in err


def test_a_timed_out_compose_command_becomes_a_stack_error_that_says_so() -> None:
    def runner(command: Sequence[str]) -> tuple[int, str, str]:
        return 124, "", "timed out after 900s"

    with pytest.raises(StackError, match="timed out after 900s"):
        DockerStack(runner=runner).states()


def test_restart_runs_docker_restart_for_the_container() -> None:
    runner = FakeRunner([ps("healthy")])

    def fake(command: Sequence[str]) -> tuple[int, str, str]:
        if command[:2] == ["docker", "restart"]:
            runner.commands.append(list(command))
            return 0, "", ""
        return runner(command)

    DockerStack(runner=fake).restart("paladin-node1")
    assert ["docker", "restart", "--time", "10", "paladin-node1"] in runner.commands


def test_restart_of_a_missing_container_raises_stack_error() -> None:
    def runner(command: Sequence[str]) -> tuple[int, str, str]:
        return 1, "", "No such container: nope"

    with pytest.raises(StackError, match="No such container"):
        DockerStack(runner=runner).restart("nope")
