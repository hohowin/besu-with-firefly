import json
from collections.abc import Callable
from pathlib import Path
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


def test_ensure_interface_registers_a_new_interface_from_the_generated_one() -> None:
    generated = {"name": "coin", "version": "1.0.0", "methods": [], "events": []}
    transport = FakeTransport(
        (200, []),  # no interface called coin yet
        (200, generated),  # generate
        (200, {"id": "if1", "name": "coin", "version": "1.0.0"}),  # register
    )
    assert client(transport).ensure_interface("coin", "1.0.0", [{"type": "function"}]) == "if1"
    assert transport.requests[0][:2] == (
        "GET",
        "/api/v1/namespaces/default/contracts/interfaces?name=coin&version=1.0.0",
    )
    generate = transport.requests[1]
    assert generate[1] == "/api/v1/namespaces/default/contracts/interfaces/generate"
    assert generate[2]["name"] == "coin" and generate[2]["version"] == "1.0.0"
    register = transport.requests[2]
    assert register[:2] == ("POST", "/api/v1/namespaces/default/contracts/interfaces?confirm=true")
    assert register[2] == generated


def test_ensure_interface_reuses_one_that_is_already_registered() -> None:
    transport = FakeTransport((200, [{"id": "if9", "name": "coin", "version": "1.0.0"}]))
    assert client(transport).ensure_interface("coin", "1.0.0", []) == "if9"
    assert len(transport.requests) == 1


def test_ensure_api_creates_a_missing_api() -> None:
    transport = FakeTransport((200, []), (200, {"id": "api1", "name": "coin"}))
    assert client(transport).ensure_api("coin", "if1", ADDRESS) == "api1"
    create = transport.requests[1]
    assert create[:2] == ("POST", "/api/v1/namespaces/default/apis?confirm=true")
    assert create[2] == {
        "name": "coin",
        "interface": {"id": "if1"},
        "location": {"address": ADDRESS},
    }


def test_ensure_api_reuses_an_api_for_the_same_interface_and_address() -> None:
    existing = {
        "id": "api1", "name": "coin", "interface": {"id": "if1"},
        "location": {"address": ADDRESS.upper().replace("0X", "0x")},
    }  # fmt: skip
    transport = FakeTransport((200, [existing]))
    assert client(transport).ensure_api("coin", "if1", ADDRESS) == "api1"
    assert len(transport.requests) == 1


def test_ensure_api_refuses_an_api_that_points_somewhere_else() -> None:
    other = {
        "id": "api1", "name": "coin", "interface": {"id": "if1"},
        "location": {"address": "0x" + "11" * 20},
    }  # fmt: skip
    with pytest.raises(FireflyError, match=r"API 'coin' already exists.*reset"):
        client(FakeTransport((200, [other]))).ensure_api("coin", "if1", ADDRESS)


def test_api_query_returns_the_output_value() -> None:
    transport = FakeTransport((200, {"output": "Coin"}))
    assert client(transport).api_query("coin", "name", {}) == "Coin"
    assert transport.requests[0][:2] == ("POST", "/api/v1/namespaces/default/apis/coin/query/name")
    assert transport.requests[0][2] == {"input": {}}


def test_api_invoke_posts_with_confirm_and_returns_the_operation() -> None:
    transport = FakeTransport((200, {"id": "op1", "status": "Succeeded"}))
    op = client(transport).api_invoke("coin", "unpause", {}, key="0xk")
    assert op.succeeded
    method, path, body = transport.requests[0]
    assert (method, path) == (
        "POST",
        "/api/v1/namespaces/default/apis/coin/invoke/unpause?confirm=true",
    )
    assert body == {"input": {}, "key": "0xk"}


REVERT = {
    "error": (
        "FF10111: Error from ethereum connector: "
        'FF23021: EVM reverted: Error("Transfer not possible")'
    )
}


def test_a_revert_is_its_own_error_with_the_reason_and_is_not_transient() -> None:
    from src.adapters.firefly import Reverted
    from src.core.firefly.operations import is_transient

    with pytest.raises(Reverted) as raised:
        client(FakeTransport((500, REVERT))).invoke(ADDRESS, METHOD, {}, key="0xk")
    assert raised.value.reason == "Transfer not possible"
    assert "EVM reverted" in str(raised.value)
    assert not is_transient(str(raised.value))


def test_a_revert_through_a_contract_api_is_also_reverted() -> None:
    from src.adapters.firefly import Reverted

    with pytest.raises(Reverted, match="Transfer not possible"):
        client(FakeTransport((500, REVERT))).api_invoke("coin", "transfer", {}, key="0xk")


def test_a_reverted_error_is_still_a_firefly_error() -> None:
    from src.adapters.firefly import Reverted

    assert issubclass(Reverted, FireflyError)


TIMEOUT = {
    "error": (
        "FF10111: Error from ethereum connector: : "
        'Post "http://firefly-evmconnect:5008/": context deadline exceeded'
    )
}


def test_a_read_that_times_out_is_retried_and_returns_the_later_answer() -> None:
    transport = FakeTransport((500, TIMEOUT), (500, TIMEOUT), (200, {"output": "Coin"}))
    assert client(transport).api_query("coin", "name", {}) == "Coin"
    assert len(transport.requests) == 3


def test_every_kind_of_read_is_retried() -> None:
    reads: list[tuple[Callable[[FireflyClient], object], Any]] = [
        (lambda c: c.status(), {"namespace": {"name": "default"}}),
        (lambda c: c.query(ADDRESS, METHOD, {}), {"": "1"}),
        (lambda c: c.get_operation("op"), {"id": "op", "status": "Succeeded"}),
        (lambda c: c.transaction_operations("tx"), []),
        (lambda c: c.generate_interface([]), {"methods": []}),
    ]
    for call, ok in reads:
        transport = FakeTransport((500, TIMEOUT), (200, ok))
        call(client(transport))
        assert len(transport.requests) == 2


def test_a_read_that_keeps_timing_out_gives_up_with_the_error() -> None:
    transport = FakeTransport((500, TIMEOUT))
    with pytest.raises(FireflyError, match="context deadline exceeded"):
        client(transport).api_query("coin", "name", {})
    assert len(transport.requests) == 4  # the first try and three retries


def test_a_read_that_fails_for_another_reason_is_not_retried() -> None:
    transport = FakeTransport((400, {"error": "FF10111: bad input"}))
    with pytest.raises(FireflyError, match="bad input"):
        client(transport).api_query("coin", "name", {})
    assert len(transport.requests) == 1


def test_a_read_that_reverts_is_not_retried() -> None:
    from src.adapters.firefly import Reverted

    transport = FakeTransport((500, REVERT))
    with pytest.raises(Reverted):
        client(transport).api_query("coin", "name", {})
    assert len(transport.requests) == 1


def test_a_write_that_times_out_is_not_retried_by_the_client() -> None:
    # Retrying a write is the caller's job, under an idempotency key (see trex_deploy.submit).
    transport = FakeTransport((500, TIMEOUT))
    with pytest.raises(FireflyError, match="context deadline exceeded"):
        client(transport).invoke(ADDRESS, METHOD, {}, key="0xk")
    assert len(transport.requests) == 1


def test_transaction_events_reads_the_events_of_a_transaction_from_a_real_response() -> None:
    recorded = json.loads(
        (Path(__file__).parent / "recorded" / "events_by_tx.json").read_text(encoding="utf-8")
    )
    transport = FakeTransport((200, recorded))
    events = client(transport).transaction_events("tx1")
    assert [e.type for e in events] == ["transaction_submitted", "blockchain_invoke_op_succeeded"]
    assert transport.requests == [("GET", "/api/v1/namespaces/default/events?tx=tx1", None)]
