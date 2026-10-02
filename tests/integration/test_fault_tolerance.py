"""QBFT with 4 validators tolerates exactly one failure (n = 3f + 1, f = 1).

Validators publish no RPC, so progress is read from their logs. Task 9 repeats the single-failure
proof through the RPC nodes once they exist.
"""

import contextlib
import time
from collections.abc import Iterator

import pytest

from src.adapters.docker_stack import DockerStack, StackError
from src.core.network.besu_logs import latest_block_number
from tests.support.polling import wait_for

VALIDATORS = [f"besu-validator-{n}" for n in (1, 2, 3, 4)]
OBSERVER = "besu-validator-1"

pytestmark = pytest.mark.integration


def latest(stack: DockerStack, validator: str) -> int:
    block = latest_block_number(stack.logs(validator))
    assert block is not None, f"{validator} has not logged a block yet"
    return block


@pytest.fixture
def restore_validators(stack: DockerStack) -> Iterator[None]:
    """Whatever a test stops, start it again so later tests see a healthy network."""
    yield
    for name in VALIDATORS:
        with contextlib.suppress(StackError):  # already running
            stack.start(name)
    stack.up(wait_timeout=120)
    resumed_from = latest(stack, OBSERVER)
    wait_for(
        lambda: latest(stack, OBSERVER) > resumed_from or None,
        describe="block production to resume after restoring the validators",
        timeout=90,
    )


def test_one_failed_validator_does_not_halt_the_chain_and_it_rejoins(
    stack: DockerStack, restore_validators: None
) -> None:
    stack.stop("besu-validator-4")
    at_stop = latest(stack, OBSERVER)

    # 3 of 4 validators can still commit, so new blocks must keep coming.
    wait_for(
        lambda: latest(stack, OBSERVER) >= at_stop + 2 or None,
        describe=f"2 new blocks on {OBSERVER} after besu-validator-4 stopped",
        timeout=30,
        interval=1,
    )

    # The stopped validator rejoins and catches up.
    stopped_at = latest(stack, "besu-validator-4")
    stack.start("besu-validator-4")

    def caught_up() -> int | None:
        mine = latest(stack, "besu-validator-4")
        return mine if mine > stopped_at and mine >= latest(stack, OBSERVER) - 3 else None

    wait_for(caught_up, describe="besu-validator-4 to sync and keep up", timeout=90)


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
