"""Run the Compose stack through the Docker CLI: start it, wait until healthy, read logs.

The command runner, sleep and clock are injected so the waiting logic is testable without Docker.
"""

import re
import subprocess
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from src.core.network.health import ContainerState, all_healthy, parse_compose_ps

REPO_ROOT = Path(__file__).resolve().parents[2]
_ANSI = re.compile(r"\x1b\[[0-9;]*m")

# Runs a command and returns (exit code, stdout, stderr).
Runner = Callable[[Sequence[str]], tuple[int, str, str]]


class StackError(Exception):
    """A Docker or Compose command failed, or the stack did not become healthy in time."""


def subprocess_runner(cwd: Path = REPO_ROOT, timeout: float = 300) -> Runner:
    def run(command: Sequence[str]) -> tuple[int, str, str]:
        proc = subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr

    return run


class DockerStack:
    def __init__(
        self,
        runner: Runner | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._run = runner or subprocess_runner()
        self._sleep = sleep
        self._clock = clock

    def _compose(self, *args: str) -> str:
        return self._checked(["docker", "compose", *args])

    def _checked(self, command: Sequence[str]) -> str:
        code, out, err = self._run(command)
        if code != 0:
            raise StackError(f"`{' '.join(command)}` failed ({code}): {err.strip() or out.strip()}")
        return out

    def services(self) -> list[str]:
        return [s for s in self._compose("config", "--services").split() if s]

    def states(self) -> list[ContainerState]:
        return parse_compose_ps(self._compose("ps", "--format", "json"))

    def up(self, wait_timeout: float = 120.0, poll_seconds: float = 2.0) -> list[ContainerState]:
        """Start every service and wait until all are running and healthy."""
        expected = self.services()
        self._compose("up", "-d")
        deadline = self._clock() + wait_timeout
        while True:
            states = self.states()
            if all_healthy(states, expected):
                return states
            if self._clock() >= deadline:
                by_service = {s.service: s for s in states}
                waiting = [
                    f"{name} is {by_service[name].health or by_service[name].state}"
                    if name in by_service
                    else f"{name} is missing"
                    for name in expected
                    if name not in by_service or by_service[name].health != "healthy"
                ]
                raise StackError(f"not healthy after {wait_timeout:g}s: {', '.join(waiting)}")
            self._sleep(poll_seconds)

    def stop(self, container: str) -> None:
        """Stop one container (it stays stopped; the stack has no restart policy)."""
        self._checked(["docker", "stop", "--time", "10", container])

    def start(self, container: str) -> None:
        self._checked(["docker", "start", container])

    def started_at(self, container: str) -> str:
        """The container's last start time. It changes if the container restarts."""
        out = self._checked(
            ["docker", "inspect", "--format", "{{.State.StartedAt}}", container]
        )
        return out.strip()

    def published_ports(self, container: str) -> list[str]:
        """Host port mappings, one `PORT/tcp -> HOST:PORT` line each. Empty if none."""
        code, out, _err = self._run(["docker", "port", container])
        return [line.strip() for line in out.splitlines() if line.strip()] if code == 0 else []

    def logs(self, container: str, tail: int | None = None) -> str:
        """Container logs (stdout and stderr) with colour codes removed."""
        command = ["docker", "logs", container]
        if tail is not None:
            command += ["--tail", str(tail)]
        code, out, err = self._run(command)
        if code != 0:
            raise StackError(f"`docker logs {container}` failed: {err.strip()}")
        return _ANSI.sub("", out + err)
