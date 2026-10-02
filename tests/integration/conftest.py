import pytest

from src.adapters.docker_stack import DockerStack


@pytest.fixture(scope="session")
def stack() -> DockerStack:
    """The running stack. Starts it if needed and waits until every service is healthy."""
    docker_stack = DockerStack()
    docker_stack.up(wait_timeout=180)
    return docker_stack
