from typing import Any

import pytest

from src.adapters.firefly import (
    AlreadySubmitted,
    FireflyClient,
    FireflyError,
    OperationFailed,
    OperationTimeout,
)

ADDRESS = "0x" + "cd" * 20
METHOD = {"name": "get", "params": [], "returns": []}


class FakeTransport:
    """Replays scripted (status, body) answers and records every request."""

    def __init__(self, *answers: tuple[int, Any]) -> None:
        self.answers = list(answers)
        self.requests: list[tuple[str, str, Any]] = []

    def __call__(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        self.requests.append((method, path, body))
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


def client(transport: FakeTransport) -> FireflyClient:
    ticks = iter(range(10_000))
    return FireflyClient(transport, sleep=lambda _s: None, clock=lambda: float(next(ticks)))


def test_status_returns_the_status_document() -> None:
    transport = FakeTransport((200, {"namespace": {"name": "default"}}))
    assert client(transport).status()["namespace"]["name"] == "default"
    assert transport.requests == [("GET", "/api/v1/status", None)]


def test_deploy_posts_to_the_deploy_api_with_confirm_and_returns_the_address() -> None:
    op = {
        "id": "op1",
        "status": "Succeeded",
        "tx": "tx1",
        "output": {"contractLocation": {"address": ADDRESS}},
    }
    transport = FakeTransport((200, op))
    result = client(transport).deploy("0x6080", [], [], key="0xk", idempotency_key="d1")
    assert result.address == ADDRESS
    assert result.operation.id == "op1"
    method, path, body = transport.requests[0]
    assert (method, path) == ("POST", "/api/v1/namespaces/default/contracts/deploy?confirm=true")
    assert body["idempotencyKey"] == "d1" and body["key"] == "0xk"


def test_a_deploy_without_an_address_in_the_output_is_an_error() -> None:
    transport = FakeTransport((200, {"id": "op1", "status": "Succeeded", "output": {}}))
    with pytest.raises(FireflyError, match="no contract address"):
        client(transport).deploy("0x6080", [], [], key="0xk")


def test_a_succeeded_invoke_returns_the_operation() -> None:
    transport = FakeTransport((200, {"id": "op1", "status": "Succeeded", "tx": "tx1"}))
    op = client(transport).invoke(ADDRESS, METHOD, {}, key="0xk", idempotency_key="i1")
    assert op.succeeded
    assert transport.requests[0][1] == "/api/v1/namespaces/default/contracts/invoke?confirm=true"


def test_a_failed_operation_raises_with_firefly_error_text_and_the_operation_id() -> None:
    answer = {"id": "op9", "status": "Failed", "error": "execution reverted"}
    with pytest.raises(OperationFailed, match=r"op9.*execution reverted") as raised:
        client(FakeTransport((200, answer))).invoke(ADDRESS, METHOD, {}, key="0xk")
    assert raised.value.operation_id == "op9"


def test_a_409_ff10431_raises_already_submitted_with_the_original_transaction() -> None:
    body = {"error": "FF10431: Idempotency key 'i1' already used for transaction 'tx-first'"}
    with pytest.raises(AlreadySubmitted) as raised:
        client(FakeTransport((409, body))).invoke(
            ADDRESS, METHOD, {}, key="0xk", idempotency_key="i1"
        )
    assert raised.value.transaction_id == "tx-first"


def test_a_pending_operation_is_polled_until_it_succeeds() -> None:
    transport = FakeTransport(
        (202, {"id": "op5", "status": "Pending"}),
        (200, {"id": "op5", "status": "Pending"}),
        (200, {"id": "op5", "status": "Succeeded", "tx": "tx5"}),
    )
    op = client(transport).invoke(ADDRESS, METHOD, {}, key="0xk")
    assert op.succeeded
    polled = [request[1] for request in transport.requests[1:]]
    assert polled == ["/api/v1/namespaces/default/operations/op5"] * 2


def test_an_operation_that_never_finishes_times_out_with_its_id_and_last_status() -> None:
    transport = FakeTransport((202, {"id": "op6", "status": "Pending"}))
    with pytest.raises(OperationTimeout, match=r"op6.*Pending"):
        client(transport).invoke(ADDRESS, METHOD, {}, key="0xk", timeout=5)


def test_other_http_errors_become_firefly_errors_with_the_message() -> None:
    transport = FakeTransport((400, {"error": "FF10111: bad input"}))
    with pytest.raises(FireflyError, match="FF10111: bad input"):
        client(transport).invoke(ADDRESS, METHOD, {}, key="0xk")


def test_query_returns_the_output_without_a_signing_key() -> None:
    transport = FakeTransport((200, {"": "42"}))
    assert client(transport).query(ADDRESS, METHOD, {}) == {"": "42"}
    method, path, body = transport.requests[0]
    assert (method, path) == ("POST", "/api/v1/namespaces/default/contracts/query")
    assert "key" not in body


def test_get_operation_reads_one_operation() -> None:
    transport = FakeTransport((200, {"id": "op7", "status": "Succeeded"}))
    assert client(transport).get_operation("op7").succeeded
    assert transport.requests[0][:2] == ("GET", "/api/v1/namespaces/default/operations/op7")


def test_get_operation_of_an_unknown_id_is_a_firefly_error() -> None:
    transport = FakeTransport((404, {"error": "FF10109: not found"}))
    with pytest.raises(FireflyError, match="FF10109"):
        client(transport).get_operation("nope")


def test_a_transport_failure_is_a_firefly_error_naming_the_request() -> None:
    def broken(method: str, path: str, body: Any = None) -> tuple[int, Any]:
        raise ConnectionRefusedError("refused")

    with pytest.raises(FireflyError, match=r"GET /api/v1/status.*refused"):
        FireflyClient(broken).status()


def test_transaction_operations_lists_the_operations_of_a_transaction() -> None:
    transport = FakeTransport(
        (200, [{"id": "op1", "status": "Failed", "error": "FF10111: EVM reverted"}])
    )
    operations = client(transport).transaction_operations("tx1")
    assert [(o.id, o.status, o.error) for o in operations] == [
        ("op1", "Failed", "FF10111: EVM reverted")
    ]
    expected = "/api/v1/namespaces/default/transactions/tx1/operations"
    assert transport.requests[0][:2] == ("GET", expected)
