from typing import Any

import pytest

from src.adapters.paladin import (
    PaladinClient,
    ReceiptTimeout,
    TransactionFailed,
)
from src.core.paladin.rpc import PaladinRpcError

URLS = {"node1": "http://n1", "node2": "http://n2"}


class FakeTransport:
    """Replays scripted replies (or raises scripted exceptions) and records every request."""

    def __init__(self, *answers: Any) -> None:
        self.answers = list(answers)
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        self.requests.append((url, body))
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return dict(answer)


def ok(result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": 1, "result": result}


def client(transport: FakeTransport) -> PaladinClient:
    ticks = iter(range(10_000))
    return PaladinClient(URLS, transport, sleep=lambda _s: None, clock=lambda: float(next(ticks)))


def test_call_posts_to_the_right_node_and_returns_the_result() -> None:
    transport = FakeTransport(ok("node2"))
    assert client(transport).call("node2", "transport_nodeName") == "node2"
    url, body = transport.requests[0]
    assert url == "http://n2"
    assert body["method"] == "transport_nodeName" and body["params"] == []


def test_an_unknown_node_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown Paladin node 'node9'"):
        client(FakeTransport(ok(1))).call("node9", "x")


def test_a_json_rpc_error_raises_with_paladins_message() -> None:
    transport = FakeTransport(
        {"jsonrpc": "2.0", "id": 1, "error": {"code": 1, "message": "PD1: no"}}
    )
    with pytest.raises(PaladinRpcError, match="PD1: no"):
        client(transport).call("node1", "x")
    assert len(transport.requests) == 1  # an error from the node is not retried


def test_a_read_that_times_out_is_retried() -> None:
    transport = FakeTransport(TimeoutError("timed out"), TimeoutError("timed out"), ok("node1"))
    assert client(transport).call("node1", "transport_nodeName") == "node1"
    assert len(transport.requests) == 3


def test_a_read_that_keeps_timing_out_gives_up_with_the_error() -> None:
    transport = FakeTransport(ConnectionRefusedError("connection refused"))
    with pytest.raises(PaladinRpcError, match="connection refused"):
        client(transport).call("node1", "x")
    assert len(transport.requests) == 4  # the first try and three retries


def test_send_transaction_is_never_retried_because_it_is_not_idempotent() -> None:
    transport = FakeTransport(TimeoutError("timed out"))
    with pytest.raises(PaladinRpcError, match="timed out"):
        client(transport).send_transaction("node1", {"type": "public"})
    assert len(transport.requests) == 1


def test_a_successful_transaction_returns_its_receipt() -> None:
    receipt = {"id": "tx1", "success": True, "contractAddress": "0xabc"}
    transport = FakeTransport(ok("tx1"), ok(None), ok(None), ok(receipt))
    result = client(transport).send_and_wait("node1", {"type": "public"})
    assert result == receipt
    methods = [body["method"] for _url, body in transport.requests]
    assert methods == [
        "ptx_sendTransaction",
        "ptx_getTransactionReceipt",
        "ptx_getTransactionReceipt",
        "ptx_getTransactionReceipt",
    ]
    assert transport.requests[1][1]["params"] == ["tx1"]


def test_a_failed_receipt_raises_with_its_text_and_the_transaction_id() -> None:
    receipt = {"id": "tx9", "success": False, "failureMessage": "PD011513: reverted"}
    transport = FakeTransport(ok("tx9"), ok(receipt))
    with pytest.raises(TransactionFailed, match=r"tx9.*PD011513: reverted") as raised:
        client(transport).send_and_wait("node1", {"type": "public"})
    assert raised.value.transaction_id == "tx9"


def test_a_receipt_that_never_arrives_times_out_naming_the_transaction() -> None:
    transport = FakeTransport(ok("tx5"), ok(None))
    with pytest.raises(ReceiptTimeout, match="tx5") as raised:
        client(transport).send_and_wait("node1", {"type": "public"}, timeout=5)
    assert raised.value.transaction_id == "tx5"


def test_a_private_call_uses_ptx_call() -> None:
    transport = FakeTransport(ok({"totalBalance": "40"}))
    result = client(transport).private_call("node2", {"domain": "noto", "function": "balanceOf"})
    assert result == {"totalBalance": "40"}
    assert transport.requests[0][1]["method"] == "ptx_call"
    assert transport.requests[0][0] == "http://n2"
