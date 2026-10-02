import json

import pytest

from src.core.network.health import ContainerState, all_healthy, parse_compose_ps

SERVICES = ["besu-validator-1", "besu-validator-2"]


def ndjson(*states: tuple[str, str, str]) -> str:
    return "\n".join(
        json.dumps({"Name": n, "Service": n, "State": state, "Health": health, "ExitCode": 0})
        for n, state, health in states
    )


def test_parse_reads_one_json_object_per_line() -> None:
    out = ndjson(
        ("besu-validator-1", "running", "healthy"), ("besu-validator-2", "running", "starting")
    )
    assert parse_compose_ps(out) == [
        ContainerState("besu-validator-1", "running", "healthy"),
        ContainerState("besu-validator-2", "running", "starting"),
    ]


def test_parse_also_accepts_a_json_array() -> None:
    array = json.dumps([{"Service": "a", "State": "running", "Health": "healthy"}])
    assert parse_compose_ps(array) == [ContainerState("a", "running", "healthy")]


def test_parse_of_empty_output_is_an_empty_list() -> None:
    assert parse_compose_ps("") == []
    assert parse_compose_ps("\n  \n") == []


def test_parse_rejects_output_that_is_not_json() -> None:
    with pytest.raises(ValueError, match="docker compose ps"):
        parse_compose_ps("not json")


def test_all_healthy_requires_every_expected_service_to_be_running_and_healthy() -> None:
    ok = parse_compose_ps(
        ndjson(
            ("besu-validator-1", "running", "healthy"),
            ("besu-validator-2", "running", "healthy"),
        )
    )
    assert all_healthy(ok, SERVICES)


def test_all_healthy_is_false_while_one_is_still_starting() -> None:
    states = parse_compose_ps(
        ndjson(
            ("besu-validator-1", "running", "healthy"),
            ("besu-validator-2", "running", "starting"),
        )
    )
    assert not all_healthy(states, SERVICES)


def test_all_healthy_is_false_when_a_service_is_missing_or_exited() -> None:
    missing = parse_compose_ps(ndjson(("besu-validator-1", "running", "healthy")))
    exited = parse_compose_ps(
        ndjson(("besu-validator-1", "running", "healthy"), ("besu-validator-2", "exited", ""))
    )
    assert not all_healthy(missing, SERVICES)
    assert not all_healthy(exited, SERVICES)


def test_nodes_without_blocks_names_the_nodes_still_at_genesis_or_unreachable() -> None:
    from src.core.network.health import nodes_without_blocks

    assert nodes_without_blocks({"anson": 3, "beatrice": 1}) == []
    assert nodes_without_blocks({"anson": 0, "beatrice": 5}) == ["anson"]
    assert nodes_without_blocks({"anson": None, "beatrice": 0}) == ["anson", "beatrice"]
    assert nodes_without_blocks({}) == []
