from typing import Any

import pytest

from src.core.paladin.registry import (
    TRANSPORT_PROPERTY,
    ZERO_HASH,
    RegisterNode,
    SetTransport,
    registry_steps,
)

NODES = ("node1", "node2", "node3")
DETAILS = {n: f'{{"endpoint":"dns:///paladin-{n}:9000"}}' for n in NODES}
ROOT: dict[str, Any] = {
    "name": "root",
    "id": "0x" + "00" * 32,
    "properties": {"$owner": "0x" + "ab" * 20},
}


def entry(node: str, details: str | None = None) -> dict[str, object]:
    properties: dict[str, str] = {"$owner": "0x" + "cd" * 20}
    if details is not None:
        properties[TRANSPORT_PROPERTY] = details
    return {"name": node, "id": "0x" + node[-1] * 64, "properties": properties}


def test_nothing_registered_registers_every_node_first_and_then_sets_their_transports() -> None:
    steps = registry_steps(NODES, [ROOT], DETAILS)
    assert steps == [
        RegisterNode("node1"),
        RegisterNode("node2"),
        RegisterNode("node3"),
        SetTransport("node1"),
        SetTransport("node2"),
        SetTransport("node3"),
    ]


def test_a_registered_node_without_a_transport_only_gets_its_transport() -> None:
    entries = [
        ROOT,
        entry("node1"),
        entry("node2", DETAILS["node2"]),
        entry("node3", DETAILS["node3"]),
    ]
    assert registry_steps(NODES, entries, DETAILS) == [SetTransport("node1")]


def test_everything_in_place_needs_nothing() -> None:
    entries = [ROOT, *(entry(n, DETAILS[n]) for n in NODES)]
    assert registry_steps(NODES, entries, DETAILS) == []


def test_a_transport_that_no_longer_matches_is_set_again() -> None:
    entries = [ROOT, *(entry(n, DETAILS[n]) for n in NODES)]
    entries[2] = entry("node2", '{"endpoint":"dns:///old:9000"}')
    assert registry_steps(NODES, entries, DETAILS) == [SetTransport("node2")]


def test_the_root_entry_is_never_touched() -> None:
    steps = registry_steps(("node1",), [ROOT], {"node1": DETAILS["node1"]})
    assert all(step.name != "root" for step in steps)


def test_a_node_without_transport_details_is_rejected() -> None:
    with pytest.raises(ValueError, match="no transport details for node2"):
        registry_steps(NODES, [ROOT], {"node1": "x", "node3": "y"})


def test_the_constants_match_the_registry_contract() -> None:
    assert TRANSPORT_PROPERTY == "transport.grpc"
    assert ZERO_HASH == "0x" + "00" * 32
