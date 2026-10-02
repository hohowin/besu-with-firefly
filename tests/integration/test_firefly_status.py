"""FireFly in gateway mode: its four containers run and it reports ready."""

import json
import subprocess
from typing import Any

import pytest

from src.adapters.docker_stack import REPO_ROOT, DockerStack
from tests.support.firefly import ff_get
from tests.support.polling import wait_for
from tests.support.rpc import RPC_ANSON, block_number

FIREFLY_SERVICES = ["firefly-postgres", "firefly-signer", "firefly-evmconnect", "firefly-core"]

pytestmark = pytest.mark.integration


def test_the_four_firefly_containers_are_running_and_healthy(stack: DockerStack) -> None:
    states = {s.service: s for s in stack.states()}
    for name in FIREFLY_SERVICES:
        assert name in states, f"{name} is not part of the stack"
        assert (states[name].state, states[name].health) == ("running", "healthy"), name


def test_firefly_status_reports_the_default_namespace_in_gateway_mode(stack: DockerStack) -> None:
    status = wait_for(
        lambda: ff_get("/api/v1/status").get("namespace"),
        describe="FireFly /api/v1/status to answer",
        timeout=120,
    )
    assert status["name"] == "default"
    full = ff_get("/api/v1/status")
    assert full["multiparty"]["enabled"] is False
    assert [p["pluginType"] for p in full["plugins"]["blockchain"]] == ["ethereum"]


def signer_rpc(method: str) -> Any:
    """Call the signer's JSON-RPC from inside its own container (it publishes no port)."""
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": [], "id": 1})
    result = subprocess.run(
        ["docker", "exec", "firefly-signer", "curl", "-sf", "-X", "POST",
         "-H", "Content-Type: application/json", "--data", body, "http://localhost:8545"],
        capture_output=True, text=True, timeout=30, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["result"]


def test_the_signer_holds_the_three_demo_wallets(stack: DockerStack) -> None:
    wallets = json.loads(
        (REPO_ROOT / "network-config" / "wallets.json").read_text(encoding="utf-8")
    )["wallets"]
    assert [w["name"] for w in wallets] == ["admin", "anson", "beatrice"]
    assert {a.lower() for a in signer_rpc("eth_accounts")} == {w["address"] for w in wallets}


def test_firefly_reaches_our_chain_through_the_rpc_node_not_a_node_of_its_own(
    stack: DockerStack,
) -> None:
    # The signer proxies chain reads to its backend. It reports our chain id and a height that
    # follows our RPC node, so that backend is our Besu network.
    assert int(signer_rpc("eth_chainId"), 16) == 20260916
    signer_height = int(signer_rpc("eth_blockNumber"), 16)
    assert abs(signer_height - block_number(RPC_ANSON)) <= 2
    own = [s.service for s in stack.states() if s.service.startswith("firefly-")]
    assert not any("besu" in name for name in own), "FireFly runs a Besu node of its own"


def test_the_firefly_explorer_and_swagger_are_served(stack: DockerStack) -> None:
    import urllib.request

    for path, marker in (("/ui", "<!doctype html>"), ("/api", "swagger")):
        with urllib.request.urlopen(f"http://localhost:5000{path}", timeout=20) as response:  # noqa: S310
            assert response.status == 200, path
            assert marker in response.read(2000).decode("utf-8", "replace").lower(), path
