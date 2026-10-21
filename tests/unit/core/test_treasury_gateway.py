from collections.abc import Mapping
from typing import Any

import pytest

from src.core.firefly.errors import (
    AlreadySubmitted,
    FireflyError,
    OperationFailed,
    Reverted,
    WriteUnconfirmed,
)
from src.core.firefly.operations import Operation
from src.core.firefly.outcome import ComplianceRevert, Failed, Pending, Succeeded
from src.core.treasury.gateway import TreasuryGateway, parse_request
from src.core.treasury.ids import request_id_from_uuid
from src.core.treasury.request import Request, Status

UUID = "123e4567-e89b-12d3-a456-426614174000"
RID = request_id_from_uuid(UUID)
WALLETS = {"ldn": "0x" + "a1" * 20, "tor": "0x" + "a2" * 20, "treasury": "0x" + "a3" * 20}

RAW = {
    "requester": WALLETS["ldn"],
    "processingDate": "20261018",
    "status": "4",
    "amountCad": "100000",
    "amountGbp": "58000",
    "ratePpm": "580000",
    "approver": WALLETS["tor"],
}
EXPECTED = Request(
    id=RID,
    requester=WALLETS["ldn"],
    amount_cad=100000,
    processing_date=20261018,
    status=Status.SETTLED,
    amount_gbp=58000,
    rate_ppm=580000,
    approver=WALLETS["tor"],
)


class FakePort:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str, dict[str, Any], str | None, str | None]] = []
        self.queries: list[tuple[str, str, dict[str, Any]]] = []
        self.write_error: Exception | None = None
        self.script: list[Exception | None] = []  # one entry per call, consumed first
        self.earlier: dict[str, list[Operation]] = {}
        self.operation = Operation("op1", "Succeeded", tx="tx1")
        self.answers: dict[tuple[str, str], Any] = {}

    def api_invoke(
        self,
        api: str,
        method: str,
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = 0,
    ) -> Operation:
        self.writes.append((api, method, dict(inputs), key, idempotency_key))
        step = self.script.pop(0) if self.script else self.write_error
        if step:
            raise step
        return self.operation

    def transaction_operations(self, transaction_id: str) -> list[Operation]:
        return self.earlier.get(transaction_id, [Operation("opx", "Succeeded")])

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        self.queries.append((api, method, dict(inputs)))
        return self.answers[(api, method)]


@pytest.fixture
def port() -> FakePort:
    return FakePort()


@pytest.fixture
def gateway(port: FakePort) -> TreasuryGateway:
    return TreasuryGateway(port, WALLETS)


# ---- writes ----


def test_create_sends_the_right_call_as_the_signer(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    outcome = gateway.create(UUID, 100000, 20261018, "ldn")
    assert isinstance(outcome, Succeeded)
    assert port.writes == [
        (
            "funding-request",
            "createRequest",
            {"id": RID, "amountCad": "100000", "processingDate": "20261018"},
            WALLETS["ldn"],
            f"{UUID}:create",
        )
    ]


@pytest.mark.parametrize(
    ("call", "method", "inputs", "signer", "action"),
    [
        (lambda g: g.approve(UUID, "tor"), "approve", {"id": RID}, "tor", "approve"),
        (
            lambda g: g.reject(UUID, "over budget", "tor"),
            "reject",
            {"id": RID, "reason": "over budget"},
            "tor",
            "reject",
        ),
        (
            lambda g: g.settle(UUID, 580000, "treasury"),
            "settle",
            {"id": RID, "ratePpm": "580000"},
            "treasury",
            "settle",
        ),
        (lambda g: g.redeem(UUID, "ldn"), "redeem", {"id": RID}, "ldn", "redeem"),
    ],
)
def test_each_write_names_the_method_signer_and_idempotency_key(
    port: FakePort, gateway: TreasuryGateway, call: Any, method: str,
    inputs: dict[str, str], signer: str, action: str,
) -> None:  # fmt: skip
    call(gateway)
    assert port.writes == [("funding-request", method, inputs, WALLETS[signer], f"{UUID}:{action}")]


def test_an_unknown_signer_is_refused_before_anything_is_sent(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    with pytest.raises(ValueError, match="mallory"):
        gateway.approve(UUID, "mallory")
    assert port.writes == []


def test_a_bad_uuid_is_refused_before_anything_is_sent(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    with pytest.raises(ValueError):
        gateway.approve("not-a-uuid", "tor")
    assert port.writes == []


def test_a_revert_becomes_a_compliance_revert(port: FakePort, gateway: TreasuryGateway) -> None:
    port.write_error = Reverted("SelfApproval", "HTTP 400: EVM reverted")
    assert gateway.approve(UUID, "ldn") == ComplianceRevert("SelfApproval")


def test_a_failed_operation_is_a_failure(port: FakePort, gateway: TreasuryGateway) -> None:
    port.write_error = OperationFailed("op9", "connector down")
    outcome = gateway.settle(UUID, 580000, "treasury")
    assert isinstance(outcome, Failed)
    assert outcome.operation_id == "op9"


def test_an_unconfirmed_write_is_pending_never_done(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    port.write_error = WriteUnconfirmed("connection dropped")
    assert isinstance(gateway.create(UUID, 100, 20261018, "ldn"), Pending)


def test_a_repeated_write_is_pending_and_names_the_first_transaction(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    port.write_error = AlreadySubmitted("tx-first")
    port.earlier["tx-first"] = [Operation("op0", "Succeeded")]
    outcome = gateway.create(UUID, 100, 20261018, "ldn")
    assert outcome == Pending(None, "tx-first", "already submitted")
    assert len(port.writes) == 1  # not sent a second time


def test_a_repeat_while_the_first_try_is_still_pending_stays_pending(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    port.write_error = AlreadySubmitted("tx-slow")
    port.earlier["tx-slow"] = [Operation("op0", "Pending")]
    assert gateway.approve(UUID, "tor") == Pending(None, "tx-slow", "already submitted")
    assert len(port.writes) == 1


def test_a_repeat_after_a_failed_first_try_is_sent_again_under_a_new_key(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    """FireFly keeps the key of a failed transaction, so the same key can never succeed. The
    first try was refused (wrong wallet, bad rate); after the cause is fixed the retry must go
    out under a new key, the same every time for the same failed transaction."""
    port.script = [AlreadySubmitted("tx-failed-1234"), None]
    port.earlier["tx-failed-1234"] = [Operation("op0", "Failed", error="reverted")]
    outcome = gateway.approve(UUID, "tor")
    assert isinstance(outcome, Succeeded)
    keys = [write[4] for write in port.writes]
    assert keys == [f"{UUID}:approve", f"{UUID}:approve-after-tx-faile"]


def test_a_second_failure_chains_to_a_third_key_and_a_refusal_is_returned_as_it_is(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    port.script = [
        AlreadySubmitted("tx-aaaaaaaa"),
        AlreadySubmitted("tx-bbbbbbbb"),
        Reverted("BadRate", "HTTP 400: EVM reverted"),
    ]
    port.earlier["tx-aaaaaaaa"] = [Operation("op1", "Failed")]
    port.earlier["tx-bbbbbbbb"] = [Operation("op2", "Failed")]
    outcome = gateway.settle(UUID, 900000, "treasury")
    assert outcome == ComplianceRevert("BadRate")
    keys = [write[4] for write in port.writes]
    assert keys == [
        f"{UUID}:settle",
        f"{UUID}:settle-after-tx-aaaaa",
        f"{UUID}:settle-after-tx-aaaaa-after-tx-bbbbb",
    ]


def test_the_retries_stop_so_a_broken_key_cannot_loop_forever(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    port.write_error = AlreadySubmitted("tx-failed-0000")
    port.earlier["tx-failed-0000"] = [Operation("op0", "Failed")]
    outcome = gateway.redeem(UUID, "ldn")
    assert isinstance(outcome, Pending)  # unknown, never reported as done
    assert 1 < len(port.writes) <= 6


def test_asking_about_the_earlier_try_can_fail_without_hiding_the_cause(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    port.write_error = AlreadySubmitted("tx-first")

    def broken(_transaction_id: str) -> list[Operation]:
        raise FireflyError("connection refused")

    port.transaction_operations = broken  # type: ignore[assignment]
    outcome = gateway.create(UUID, 100, 20261018, "ldn")
    assert isinstance(outcome, Failed) and "connection refused" in str(outcome.error)


def test_a_pending_operation_is_pending(port: FakePort, gateway: TreasuryGateway) -> None:
    port.operation = Operation("op2", "Pending", tx="tx2")
    outcome = gateway.redeem(UUID, "ldn")
    assert outcome == Pending("op2", "tx2", "Pending")


# ---- reads ----


def test_parse_request_reads_the_struct_fields() -> None:
    assert parse_request(RID, RAW) == EXPECTED


def test_parse_request_accepts_the_struct_nested_under_one_key() -> None:
    assert parse_request(RID, {"0": RAW}) == EXPECTED


def test_parse_request_accepts_a_positional_list() -> None:
    order = (
        "requester",
        "processingDate",
        "status",
        "amountCad",
        "amountGbp",
        "ratePpm",
        "approver",
    )
    values = [RAW[name] for name in order]
    assert parse_request(RID, values) == EXPECTED


def test_a_request_that_does_not_exist_is_none() -> None:
    empty = {**RAW, "status": "0", "requester": "0x" + "00" * 20}
    assert parse_request(RID, empty) is None


def test_a_zero_approver_is_none() -> None:
    open_request = {**RAW, "status": "1", "approver": "0x" + "00" * 20, "amountGbp": "0"}
    assert parse_request(RID, open_request) == Request(
        id=RID,
        requester=WALLETS["ldn"],
        amount_cad=100000,
        processing_date=20261018,
        status=Status.REQUESTED,
        amount_gbp=0,
        rate_ppm=580000,
        approver=None,
    )


def test_parse_request_refuses_something_it_does_not_understand() -> None:
    with pytest.raises(ValueError):
        parse_request(RID, "what")


def test_get_request_asks_for_the_id(port: FakePort, gateway: TreasuryGateway) -> None:
    port.answers[("funding-request", "getRequest")] = RAW
    assert gateway.get_request(UUID) == EXPECTED
    assert port.queries == [("funding-request", "getRequest", {"id": RID})]


def test_list_requests_reads_each_id_in_order(port: FakePort, gateway: TreasuryGateway) -> None:
    other = request_id_from_uuid("00000000-0000-0000-0000-000000000002")
    ids = {"0": RID, "1": other}

    class ListPort(FakePort):
        def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
            if method == "requestCount":
                return "2"
            if method == "requestIdAt":
                return ids[str(inputs["index"])]
            return RAW

    listed = TreasuryGateway(ListPort(), WALLETS).list_requests()
    assert [r.id for r in listed] == [RID, other]


def test_balances_cover_every_wallet_and_both_supplies(port: FakePort) -> None:
    def answer(api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        if method == "totalSupply":
            return {"cadc": "100000", "gbpc": "0"}[api]
        address = inputs["account"]
        return {"cadc": "100000", "gbpc": "0"}[api] if address == WALLETS["treasury"] else "0"

    port.api_query = answer  # type: ignore[method-assign]
    result = TreasuryGateway(port, WALLETS).balances()
    assert result.supply == {"cadc": 100000, "gbpc": 0}
    assert result.balances["treasury"] == {"cadc": 100000, "gbpc": 0}
    assert result.balances["ldn"] == {"cadc": 0, "gbpc": 0}
    assert set(result.balances) == {"ldn", "tor", "treasury"}


def test_a_refused_try_that_stayed_initialized_is_retried_too(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    """A write the contract refuses while the gas is estimated never becomes `Failed`: FireFly
    leaves its operation `Initialized` (seen on a live stack). It never went out, so retry."""
    port.script = [AlreadySubmitted("tx-refused-1"), None]
    port.earlier["tx-refused-1"] = [Operation("op0", "Initialized")]
    assert isinstance(gateway.approve(UUID, "tor"), Succeeded)
    assert len(port.writes) == 2


def test_a_try_that_is_pending_or_succeeded_is_never_sent_again(
    port: FakePort, gateway: TreasuryGateway
) -> None:
    for status in ("Pending", "Succeeded"):
        port.writes.clear()
        port.write_error = AlreadySubmitted("tx-live")
        port.earlier["tx-live"] = [Operation("op0", status)]
        assert gateway.approve(UUID, "tor") == Pending(None, "tx-live", "already submitted")
        assert len(port.writes) == 1
