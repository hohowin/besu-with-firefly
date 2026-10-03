import contextlib
import json
from collections.abc import Iterator
from functools import partial

import pytest

from src.adapters.docker_stack import REPO_ROOT, DockerStack, StackError
from src.adapters.rpc import chain_heights_reader
from tests.support.deploy import run_deploy
from tests.support.polling import wait_for
from tests.support.rpc import RPC_ANSON, RPC_BEATRICE, block_number

VALIDATORS = [f"besu-validator-{n}" for n in (1, 2, 3, 4)]


@pytest.fixture(scope="session")
def stack() -> DockerStack:
    """The running stack. Starts it if needed and waits until every service is healthy."""
    docker_stack = DockerStack(chain_heights=chain_heights_reader())
    docker_stack.up(wait_timeout=300)
    return docker_stack


@pytest.fixture
def restore_validators(stack: DockerStack) -> Iterator[None]:
    """Whatever a test stops, start it again, even if an assertion failed, so later tests
    see a healthy network. Waits until both RPC nodes see new blocks again.

    This is cleanup, not an assertion, so it is patient: if QBFT's round timer has doubled while
    only a quorum was alive (4, 8, 16, 32, 64, 128 s), blocks can take minutes to resume.
    """
    yield
    for name in VALIDATORS:
        with contextlib.suppress(StackError):  # already running
            stack.start(name)
    stack.up(wait_timeout=300)
    for node, url in {"besu-rpc-anson": RPC_ANSON, "besu-rpc-beatrice": RPC_BEATRICE}.items():
        resumed_from = block_number(url)
        wait_for(
            partial(_advanced_past, url, resumed_from),
            describe=f"{node} to see new blocks after restoring the validators",
            timeout=300,
        )


def _advanced_past(url: str, block: int) -> bool:
    return block_number(url) > block


@pytest.fixture(scope="module")
def deployed(stack: DockerStack) -> dict[str, str]:
    """Run `stack.py deploy` (it only does what is missing) and return the deployed addresses."""
    result = run_deploy()
    assert result.returncode == 0, f"deploy failed:\n{result.stdout}\n{result.stderr}"
    path = REPO_ROOT / "deployed-addresses.json"
    return dict(json.loads(path.read_text(encoding="utf-8")))
