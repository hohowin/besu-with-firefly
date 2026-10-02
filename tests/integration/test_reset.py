"""`stack.py reset` returns the chain to genesis and leaves nothing behind."""

import os
import subprocess
import sys
from functools import partial

import pytest

from src.adapters.docker_stack import REPO_ROOT, DockerStack
from tests.support.polling import wait_for
from tests.support.rpc import RPC_ANSON, RPC_BEATRICE, block_number

PROJECT = "besu-with-firefly"

pytestmark = pytest.mark.integration


def stack_py(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "stack.py"), *args],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        env={**os.environ, **(env or {})},
    )


def _reached(url: str, block: int) -> bool:
    return block_number(url) >= block


def docker_ids(*command: str) -> list[str]:
    result = subprocess.run(
        ["docker", *command, "-q", "--filter", f"label=com.docker.compose.project={PROJECT}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.split()


def test_reset_removes_everything_and_the_next_up_starts_from_block_zero(
    stack: DockerStack,
) -> None:
    for url in (RPC_ANSON, RPC_BEATRICE):
        wait_for(partial(_reached, url, 10), describe=f"{url} past block 10")

    result = stack_py("reset")
    assert result.returncode == 0, result.stderr
    assert "besu-validator-1" in result.stdout, result.stdout
    assert docker_ids("ps", "-a") == [], "containers remain after reset"
    assert docker_ids("volume", "ls") == [], "volumes remain after reset"

    up = stack_py("up", "--timeout", "180")
    assert up.returncode == 0, up.stderr
    for url in (RPC_ANSON, RPC_BEATRICE):
        height = wait_for(partial(block_number, url), describe=f"{url} to answer")
        assert height < 10, f"{url} is at block #{height}; the chain did not restart at genesis"


def test_reset_exits_non_zero_when_docker_is_not_reachable() -> None:
    result = stack_py("reset", env={"DOCKER_HOST": "tcp://127.0.0.1:1"})
    assert result.returncode != 0
    assert "error:" in result.stderr
