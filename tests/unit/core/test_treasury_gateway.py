from collections.abc import Mapping
from typing import Any

import pytest

from src.core.firefly.errors import AlreadySubmitted, OperationFailed, Reverted, WriteUnconfirmed
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
        if self.write_error:
            raise self.write_error
        return self.operation

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
    outcome = gateway.create(UUID, 100, 20261018, "ldn")
    assert outcome == Pending(None, "tx-first", "already submitted")


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
