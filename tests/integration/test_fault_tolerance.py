"""QBFT with 4 validators tolerates exactly one failure (n = 3f + 1, f = 1).

Validators publish no RPC, so this check reads their logs. The single-failure proof, which uses the
RPC nodes, is in test_network.py.
"""

import time

import pytest

from src.adapters.docker_stack import DockerStack
from src.core.network.besu_logs import latest_block_number

OBSERVER = "besu-validator-1"

pytestmark = [pytest.mark.integration, pytest.mark.fault_injection]


def latest(stack: DockerStack, validator: str) -> int:
    block = latest_block_number(stack.logs(validator))
    assert block is not None, f"{validator} has not logged a block yet"
    return block


def test_two_failed_validators_halt_the_chain_as_expected(
    stack: DockerStack, restore_validators: None
) -> None:
    """Accepted risk R10: with 2 of 4 validators down there is no quorum, so no new blocks."""
    stack.stop("besu-validator-3")
    stack.stop("besu-validator-4")
    time.sleep(8)  # let an in-flight block finish
    halted_at = latest(stack, OBSERVER)

    for _ in range(10):  # 30 seconds
        time.sleep(3)
        assert latest(stack, OBSERVER) == halted_at, "a block was produced without a quorum"
