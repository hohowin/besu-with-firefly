import json

import pytest

from src.adapters.docker_stack import REPO_ROOT, DockerStack
from src.adapters.rpc import chain_heights_reader
from tests.support.deploy import run_deploy


@pytest.fixture(scope="session")
def stack() -> DockerStack:
    """The running stack. Starts it if needed and waits until every service is healthy."""
    docker_stack = DockerStack(chain_heights=chain_heights_reader())
    docker_stack.up(wait_timeout=300)
    return docker_stack


@pytest.fixture(scope="module")
def deployed(stack: DockerStack) -> dict[str, str]:
    """Run `stack.py deploy` (it only does what is missing) and return the deployed addresses."""
    result = run_deploy()
    assert result.returncode == 0, f"deploy failed:\n{result.stdout}\n{result.stderr}"
    path = REPO_ROOT / "deployed-addresses.json"
    return dict(json.loads(path.read_text(encoding="utf-8")))
