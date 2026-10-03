"""The QBFT validator: healthy, peered with the RPC node, producing blocks, closed to the host."""

import subprocess
import time
from functools import partial

import pytest

from src.adapters.docker_stack import REPO_ROOT, DockerStack
from src.core.network.besu_logs import latest_block_number
from tests.support.polling import wait_for
from tests.support.rpc import RPC_ANSON, peer_public_keys

VALIDATORS = ["besu-validator-1"]

pytestmark = pytest.mark.integration


def test_compose_file_is_valid() -> None:
    result = subprocess.run(
        ["docker", "compose", "config", "-q"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_the_validator_is_running_and_healthy(stack: DockerStack) -> None:
    states = {s.service: s for s in stack.states()}
    for name in VALIDATORS:
        assert name in states, f"{name} is not part of the stack"
        assert (states[name].state, states[name].health) == ("running", "healthy"), name


@pytest.mark.parametrize("validator", VALIDATORS)
def test_each_validator_is_peered_with_the_rpc_node(stack: DockerStack, validator: str) -> None:
    """Validators publish no RPC and Besu only logs peer counts at start-up, so the RPC node
    vouches for them: a validator that is in its peer list is connected to the network."""
    public_key = (
        (REPO_ROOT / "network-config" / "validator-keys" / f"validator-{validator[-1]}" / "key.pub")
        .read_text(encoding="utf-8")
        .strip()
        .removeprefix("0x")
        .lower()
    )
    wait_for(
        partial(_is_peer, RPC_ANSON, public_key),
        describe=f"besu-rpc-anson to list {validator} as a peer",
        timeout=150,  # an RPC node dials its static peers on a 60 s cycle
    )


def _is_peer(url: str, public_key: str) -> bool:
    return public_key in peer_public_keys(url)


def test_validators_keep_producing_blocks(stack: DockerStack) -> None:
    first = wait_for(
        lambda: latest_block_number(stack.logs("besu-validator-1", tail=200)),
        describe="besu-validator-1 to log a block",
        timeout=60,
    )

    def advanced() -> int | None:
        latest = latest_block_number(stack.logs("besu-validator-1", tail=200))
        return latest if latest is not None and latest > first else None

    assert wait_for(advanced, describe=f"a block after #{first}", timeout=30) > first


def test_no_validator_is_in_a_restart_loop(stack: DockerStack) -> None:
    before = {name: stack.started_at(name) for name in VALIDATORS}
    time.sleep(10)
    after = {name: stack.started_at(name) for name in VALIDATORS}
    assert before == after, "a validator restarted during the check"
    assert all(s.state == "running" for s in stack.states() if s.service in VALIDATORS)


@pytest.mark.parametrize("validator", VALIDATORS)
def test_validators_publish_no_ports_to_the_host(stack: DockerStack, validator: str) -> None:
    assert stack.published_ports(validator) == []
