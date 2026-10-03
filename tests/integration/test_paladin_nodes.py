"""The three Paladin nodes and their Postgres: healthy, answering and connected to Besu."""

import time

import pytest

from src.adapters.docker_stack import DockerStack
from tests.support.paladin import PALADIN_PORTS, paladin_call
from tests.support.polling import wait_for

NODES = list(PALADIN_PORTS)
SERVICES = ["paladin-postgres", *(f"paladin-{node}" for node in NODES)]

pytestmark = pytest.mark.integration


def test_postgres_and_the_three_nodes_are_running_and_healthy(stack: DockerStack) -> None:
    states = {s.service: s for s in stack.states()}
    for name in SERVICES:
        assert name in states, f"{name} is not part of the stack"
        assert (states[name].state, states[name].health) == ("running", "healthy"), name


@pytest.mark.parametrize("node", NODES)
def test_each_node_reports_its_own_name(stack: DockerStack, node: str) -> None:
    assert paladin_call(node, "transport_nodeName") == node


@pytest.mark.parametrize("node", NODES)
def test_each_node_is_connected_to_besu_and_has_indexed_blocks(
    stack: DockerStack, node: str
) -> None:
    def indexed() -> int | None:
        blocks = paladin_call(node, "bidx_queryIndexedBlocks", [{"limit": 1, "sort": ["-number"]}])
        return int(blocks[0]["number"]) if blocks else None

    height = wait_for(indexed, describe=f"{node} to index a block", timeout=120)
    assert height >= 1


@pytest.mark.parametrize("node", NODES)
def test_each_node_keeps_indexing_new_blocks(stack: DockerStack, node: str) -> None:
    def latest() -> int:
        blocks = paladin_call(node, "bidx_queryIndexedBlocks", [{"limit": 1, "sort": ["-number"]}])
        return int(blocks[0]["number"])

    first = latest()
    wait_for(
        lambda: latest() > first or None, describe=f"{node} to pass block #{first}", timeout=30
    )


def test_no_paladin_container_is_in_a_restart_loop(stack: DockerStack) -> None:
    before = {name: stack.started_at(name) for name in SERVICES}
    time.sleep(10)
    after = {name: stack.started_at(name) for name in SERVICES}
    assert before == after, "a Paladin container restarted during the check"
