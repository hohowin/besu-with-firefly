"""The Paladin client adapter against the real Paladin nodes (no Noto needed)."""

import pytest

from src.adapters.docker_stack import DockerStack
from src.adapters.paladin import PALADIN_NODES, PaladinClient, http_transport
from src.core.paladin.rpc import PaladinRpcError

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("node", list(PALADIN_NODES))
def test_each_node_reports_its_name_through_the_client(stack: DockerStack, node: str) -> None:
    client = PaladinClient(PALADIN_NODES, http_transport())
    assert client.call(node, "transport_nodeName") == node


def test_an_unsupported_method_is_an_error_with_paladins_own_message(stack: DockerStack) -> None:
    client = PaladinClient(PALADIN_NODES, http_transport())
    with pytest.raises(PaladinRpcError, match="PD020702") as raised:
        client.call("node1", "nope_nothing")
    assert raised.value.code == -32600


def test_the_receipt_of_an_unknown_transaction_is_none(stack: DockerStack) -> None:
    client = PaladinClient(PALADIN_NODES, http_transport())
    unknown = "00000000-0000-0000-0000-000000000000"
    assert client.call("node1", "ptx_getTransactionReceipt", [unknown]) is None


def test_an_unreachable_node_is_an_error_that_names_the_call_and_the_node() -> None:
    client = PaladinClient(
        {"node9": "http://127.0.0.1:1"}, http_transport(2), sleep=lambda _s: None
    )
    with pytest.raises(PaladinRpcError, match="transport_nodeName on node9"):
        client.call("node9", "transport_nodeName")
