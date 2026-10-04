"""`stack.py reset` returns everything to genesis and leaves nothing behind; `deploy` can resume."""

import json
import os
import subprocess
import sys
import time
from functools import partial

import pytest

from src.adapters.docker_stack import REPO_ROOT, DockerStack
from tests.support.deploy import run_deploy
from tests.support.firefly import ff_get
from tests.support.paladin import paladin_call
from tests.support.polling import wait_for
from tests.support.rpc import RPC_ANSON, block_number

PROJECT = "besu-with-firefly"

pytestmark = pytest.mark.integration


def stack_py(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "stack.py"), *args],
        capture_output=True,
        text=True,
        timeout=900,
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


ADDRESSES_FILE = REPO_ROOT / "deployed-addresses.json"


def test_reset_removes_everything_and_the_next_up_starts_from_block_zero(
    stack: DockerStack, deployed: dict[str, str]
) -> None:
    for url in (RPC_ANSON,):
        wait_for(partial(_reached, url, 10), describe=f"{url} past block 10")
    assert ADDRESSES_FILE.exists() and ff_get("/api/v1/namespaces/default/apis")

    result = stack_py("reset")
    assert result.returncode == 0, result.stderr
    assert "besu-validator-1" in result.stdout, result.stdout
    assert "firefly-core" in result.stdout, result.stdout
    assert "paladin-node1" in result.stdout, result.stdout
    assert not (REPO_ROOT / "paladin-runtime").exists(), "the Paladin runtime config remains"
    assert docker_ids("ps", "-a") == [], "containers remain after reset"
    assert docker_ids("volume", "ls") == [], "volumes remain after reset"
    assert not ADDRESSES_FILE.exists(), "a stale deployed-addresses.json remains after reset"

    started = time.monotonic()
    up = stack_py("up")
    assert up.returncode == 0, up.stderr
    # `up` only returns once the chain moves and FireFly is ready, so no waiting here.
    for url in (RPC_ANSON,):
        assert block_number(url) >= 1, f"{url} is still at block 0 right after `up`"
    assert ff_get("/api/v1/status")["namespace"]["name"] == "default"
    assert ff_get("/api/v1/namespaces/default/apis") == [], "a contract API survived the reset"
    assert ff_get("/api/v1/namespaces/default/contracts/interfaces") == []
    for node in ("node1", "node2", "node3"):  # Paladin starts without a domain until `deploy`
        assert paladin_call(node, "domain_listDomains") == [], f"{node} kept its Noto domain"
    # A chain restarted at genesis makes one block per 2 s, so its height cannot exceed that.
    limit = (time.monotonic() - started) / 2 + 5
    for url in (RPC_ANSON,):
        height = wait_for(partial(block_number, url), describe=f"{url} to answer")
        assert height <= limit, f"{url} is at block #{height}, above {limit:.0f}: not a new chain"


def test_reset_exits_non_zero_when_docker_is_not_reachable() -> None:
    result = stack_py("reset", env={"DOCKER_HOST": "tcp://127.0.0.1:1"})
    assert result.returncode != 0
    assert "error:" in result.stderr


def test_an_interrupted_deploy_is_finished_by_running_deploy_again(stack: DockerStack) -> None:
    """Needs a stack with nothing deployed, which the test above leaves behind."""
    if ADDRESSES_FILE.exists():
        pytest.skip("something is already deployed; this test needs a freshly reset stack")
    process = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "scripts" / "stack.py"), "deploy"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    def progressed() -> bool:
        return ADDRESSES_FILE.exists() and len(json.loads(ADDRESSES_FILE.read_text("utf-8"))) >= 3

    try:
        wait_for(progressed, describe="deploy to get 3 contracts in", timeout=300, interval=0.5)
    finally:
        process.kill()  # in the middle of the plan
        process.wait()
    partial_addresses = json.loads(ADDRESSES_FILE.read_text("utf-8"))
    assert 3 <= len(partial_addresses) < 22, "the run was not interrupted part-way"

    result = run_deploy()
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    final = json.loads(ADDRESSES_FILE.read_text("utf-8"))
    assert len(final) == 22  # 12 T-REX contracts, 6 suite contracts, 4 Paladin contracts
    assert all(final[name] == address for name, address in partial_addresses.items())

    # One token only, and a third run finds nothing left to do.
    invokes = ff_get("/api/v1/namespaces/default/operations?type=blockchain_invoke&limit=500")
    created = [
        o for o in invokes if o["status"] == "Succeeded" and "deployTREXSuite" in str(o["input"])
    ]
    assert len(created) == 1
    before = len(ff_get("/api/v1/namespaces/default/operations?limit=500"))
    assert run_deploy().returncode == 0
    assert len(ff_get("/api/v1/namespaces/default/operations?limit=500")) == before
