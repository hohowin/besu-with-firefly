"""Environment check for integration tests: Docker must be reachable."""

import subprocess

import pytest


@pytest.mark.integration
def test_docker_engine_is_reachable() -> None:
    result = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"docker is not reachable: {result.stderr.strip()}"
    assert result.stdout.strip(), "docker returned no server version"
