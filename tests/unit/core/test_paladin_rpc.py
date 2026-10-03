import pytest

from src.core.paladin.rpc import (
    PaladinRpcError,
    ReceiptState,
    classify_receipt,
    is_transient,
    request_body,
    unwrap,
)


def test_a_request_body_is_json_rpc_2() -> None:
    assert request_body("transport_nodeName", [], 7) == {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "transport_nodeName",
        "params": [],
    }


def test_unwrap_returns_the_result() -> None:
    assert unwrap({"jsonrpc": "2.0", "id": 1, "result": "node1"}) == "node1"
    assert unwrap({"jsonrpc": "2.0", "id": 1, "result": None}) is None


def test_unwrap_raises_with_paladins_own_message_and_code() -> None:
    reply = {"jsonrpc": "2.0", "id": 1, "error": {"code": -32603, "message": "PD200007: nope"}}
    with pytest.raises(PaladinRpcError, match="PD200007: nope") as raised:
        unwrap(reply)
    assert raised.value.code == -32603


def test_a_reply_that_is_not_json_rpc_is_rejected() -> None:
    with pytest.raises(PaladinRpcError, match="not a JSON-RPC reply"):
        unwrap({"hello": "world"})


def test_a_missing_receipt_is_pending() -> None:
    assert classify_receipt(None) is ReceiptState.PENDING


def test_a_receipt_is_a_success_or_a_failure() -> None:
    assert classify_receipt({"id": "tx", "success": True}) is ReceiptState.SUCCESS
    assert classify_receipt({"id": "tx", "success": False}) is ReceiptState.FAILED


@pytest.mark.parametrize(
    "message",
    [
        "Post http://localhost:8548: context deadline exceeded",
        "connection refused",
        "[Errno 111] Connection refused",
        "timed out",
        "HTTP 502: bad gateway",
    ],
)
def test_timeouts_and_dropped_connections_are_transient(message: str) -> None:
    assert is_transient(message)


@pytest.mark.parametrize(
    "message", ["PD200007: Parameter 'notary' is required", "execution reverted", "HTTP 400: bad"]
)
def test_errors_from_the_node_or_a_contract_are_not_transient(message: str) -> None:
    assert not is_transient(message)
