import json
from collections.abc import Sequence

import pytest

from src.adapters.docker_stack import DockerStack, StackError

SERVICES = "besu-validator-1\nbesu-validator-2\n"


def ps(*health: str) -> str:
    return "\n".join(
        json.dumps({"Service": f"besu-validator-{i}", "State": "running", "Health": h})
        for i, h in enumerate(health, start=1)
    )


class FakeRunner:
    """Replays canned results for each docker command and records what was run."""

    def __init__(self, ps_outputs: list[str], up_code: int = 0) -> None:
        self.ps_outputs = list(ps_outputs)
        self.up_code = up_code
        self.commands: list[list[str]] = []

    def __call__(self, command: Sequence[str]) -> tuple[int, str, str]:
        self.commands.append(list(command))
        if command[:3] == ["docker", "compose", "config"]:
            return 0, SERVICES, ""
        if command[:3] == ["docker", "compose", "up"]:
            return self.up_code, "", "boom" if self.up_code else ""
        if command[:3] == ["docker", "compose", "ps"]:
            return 0, self.ps_outputs.pop(0) if len(self.ps_outputs) > 1 else self.ps_outputs[0], ""
        raise AssertionError(f"unexpected command {command}")


def make_stack(runner: FakeRunner) -> DockerStack:
    return DockerStack(runner=runner, sleep=lambda _seconds: None, clock=iter(range(1000)).__next__)


def test_up_starts_the_stack_and_returns_once_every_service_is_healthy() -> None:
    runner = FakeRunner(
        [ps("starting", "starting"), ps("healthy", "starting"), ps("healthy", "healthy")]
    )
    states = make_stack(runner).up(wait_timeout=100)
    assert [s.service for s in states] == ["besu-validator-1", "besu-validator-2"]
    assert ["docker", "compose", "up", "-d"] in runner.commands


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
