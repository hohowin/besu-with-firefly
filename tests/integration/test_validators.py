"""The four QBFT validators: healthy, peered, producing blocks, closed to the host."""

import subprocess
import time

import pytest

from src.adapters.docker_stack import DockerStack
from src.core.network.besu_logs import latest_block_number, peer_count
from tests.support.polling import wait_for

VALIDATORS = [f"besu-validator-{n}" for n in (1, 2, 3, 4)]

pytestmark = pytest.mark.integration


def test_compose_file_is_valid() -> None:
    result = subprocess.run(
        ["docker", "compose", "config", "-q"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_all_four_validators_are_running_and_healthy(stack: DockerStack) -> None:
    states = {s.service: s for s in stack.states()}
    for name in VALIDATORS:
        assert name in states, f"{name} is not part of the stack"
        assert (states[name].state, states[name].health) == ("running", "healthy"), name


@pytest.mark.parametrize("validator", VALIDATORS)
def test_each_validator_has_at_least_three_peers(stack: DockerStack, validator: str) -> None:
    def peers() -> int | None:
        count = peer_count(stack.logs(validator, tail=200))
        return count if count is not None and count >= 3 else None

    assert wait_for(peers, describe=f"{validator} to report 3 or more peers", timeout=90) >= 3


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
