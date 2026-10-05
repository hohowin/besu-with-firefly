import pytest

from src.adapters.firefly import firefly_url
from src.adapters.paladin import paladin_nodes
from src.adapters.rpc import rpc_nodes
from src.adapters.settings import service_url


def test_an_unset_variable_gives_the_default() -> None:
    assert service_url("X_URL", "http://localhost:1", env={}) == "http://localhost:1"


def test_a_set_variable_wins_and_loses_a_trailing_slash_and_spaces() -> None:
    env = {"X_URL": "  http://firefly-core:5000/ "}
    assert service_url("X_URL", "http://localhost:1", env=env) == "http://firefly-core:5000"


@pytest.mark.parametrize("value", ["", "   ", "firefly-core:5000", "ftp://x", "http://", "http:///path"])
def test_a_blank_or_malformed_value_is_refused_naming_the_variable(value: str) -> None:
    with pytest.raises(ValueError, match="X_URL"):
        service_url("X_URL", "http://localhost:1", env={"X_URL": value})


def test_firefly_url_defaults_to_localhost_and_reads_firefly_url() -> None:
    assert firefly_url({}) == "http://localhost:5000"
    assert firefly_url({"FIREFLY_URL": "http://firefly-core:5000"}) == "http://firefly-core:5000"


def test_rpc_nodes_default_to_localhost_and_read_besu_rpc_url() -> None:
    assert rpc_nodes({}) == {"besu-rpc-anson": "http://localhost:8545"}
    assert rpc_nodes({"BESU_RPC_URL": "http://besu-rpc-anson:8545"}) == {
        "besu-rpc-anson": "http://besu-rpc-anson:8545"
    }


def test_paladin_nodes_default_to_the_published_ports_and_read_one_variable_each() -> None:
    assert paladin_nodes({}) == {
        "node1": "http://localhost:8548",
        "node2": "http://localhost:8648",
        "node3": "http://localhost:8748",
    }
    env = {"PALADIN_NODE2_URL": "http://paladin-node2:8548"}
    nodes = paladin_nodes(env)
    assert nodes["node2"] == "http://paladin-node2:8548"
    assert nodes["node1"] == "http://localhost:8548" and nodes["node3"] == "http://localhost:8748"


def test_a_bad_paladin_variable_names_itself() -> None:
    with pytest.raises(ValueError, match="PALADIN_NODE3_URL"):
        paladin_nodes({"PALADIN_NODE3_URL": "nope"})
