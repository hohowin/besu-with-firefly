"""`docker compose up` alone gives a deployed stack (the one-command route, no `stack.py`).

This test destroys the running stack and builds a new one, so it has its own marker and is not part
of `pytest -m integration`. Run it on purpose: `pytest -m fresh_stack` (about 4 minutes).
"""

import json
import subprocess

import pytest

from src.adapters.docker_stack import REPO_ROOT
from src.adapters.paladin import PALADIN_NODES, PaladinClient, http_transport
from tests.support.firefly import ff_post

pytestmark = pytest.mark.fresh_stack

NS = "/api/v1/namespaces/default"


def docker(*args: str, timeout: float = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def wipe() -> None:
    """Back to a clean clone: no containers or volumes, no files that a run leaves on the host."""
    assert docker("compose", "down", "--volumes", "--remove-orphans").returncode == 0
    for name in ("paladin-runtime", "deployed-addresses.json"):
        path = REPO_ROOT / name
        if path.is_dir():
            for child in sorted(path.rglob("*"), reverse=True):
                child.unlink() if child.is_file() else child.rmdir()
            path.rmdir()
        elif path.exists():
            path.unlink()


def anson() -> str:
    document = json.loads((REPO_ROOT / "network-config" / "wallets.json").read_text("utf-8"))
    return str(next(w["address"] for w in document["wallets"] if w["name"] == "anson"))


def test_docker_compose_up_alone_gives_a_deployed_stack() -> None:
    wipe()
    assert not (REPO_ROOT / "paladin-runtime").exists()

    up = docker("compose", "up", "-d")
    assert up.returncode == 0, up.stdout + up.stderr

    # `up -d` returns once the deployer has started; it runs for a couple of minutes more.
    waited = docker("wait", "deployer", timeout=900)
    shown = docker("logs", "deployer")
    logs = (shown.stdout + shown.stderr)[-3000:]  # the job writes its error to stderr
    assert waited.stdout.strip() == "0", f"deployer exited with {waited.stdout.strip()}:\n{logs}"

    seed = docker("inspect", "paladin-seed", "--format", "{{.State.ExitCode}}")
    assert seed.stdout.strip() == "0"
    assert (REPO_ROOT / "deployed-addresses.json").is_file()

    # What `docker compose up` produced is a working, deployed stack.
    name = ff_post(f"{NS}/apis/coin/query/name", {})["output"]
    assert name == "Coin"
    balance = ff_post(f"{NS}/apis/coin/query/balanceOf", {"input": {"_userAddress": anson()}})
    assert int(balance["output"]) == 1000 * 10**18
    client = PaladinClient(PALADIN_NODES, http_transport())
    for node in PALADIN_NODES:
        assert "noto" in client.call(node, "domain_listDomains"), node
