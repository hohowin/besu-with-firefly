from typing import Any

import pytest

from src.core.firefly.operations import Operation
from src.core.firefly.outcome import ComplianceRevert, Failed, Outcome, Pending, Succeeded
from src.core.treasury.errors import InvalidRate
from src.core.treasury.fx import Rates
from src.core.treasury.ids import request_id_from_uuid
from src.core.treasury.request import Request, Status
from src.core.treasury.service import TreasuryService

UUID = "123e4567-e89b-12d3-a456-426614174000"
RID = request_id_from_uuid(UUID)
OK = Succeeded(Operation("op1", "Succeeded", tx="tx1"))


def request(status: Status, cad: int = 100000, date: int = 20261018, rid: str = RID) -> Request:
    return Request(
        id=rid,
        requester="0xa1",
        amount_cad=cad,
        processing_date=date,
        status=status,
        amount_gbp=58000 if status in (Status.SETTLED, Status.REDEEMED) else 0,
        rate_ppm=580000 if status in (Status.SETTLED, Status.REDEEMED) else 0,
    )


class FakeGateway:
    def __init__(self, requests: list[Request]) -> None:
        self.requests = requests
        self.calls: list[tuple[Any, ...]] = []
        self.settle_outcome: Outcome = OK
        self.redeem_outcome: Outcome = OK

    def list_requests(self) -> list[Request]:
        return self.requests

    def settle(self, request_uuid: str, rate_ppm: int, signer: str) -> Outcome:
        self.calls.append(("settle", request_uuid, rate_ppm, signer))
        return self.settle_outcome

    def redeem(self, request_uuid: str, signer: str) -> Outcome:
        self.calls.append(("redeem", request_uuid, signer))
        return self.redeem_outcome


RATES = Rates({20261018: 581200}, 580000)


def service(
    gateway: FakeGateway, rates: Rates = RATES
) -> tuple[TreasuryService, list[dict[str, Any]]]:
    logs: list[dict[str, Any]] = []
    return TreasuryService(gateway, lambda: rates, logs.append), logs


def test_an_approved_request_is_settled_at_the_dated_rate_then_redeemed() -> None:
    gateway = FakeGateway([request(Status.APPROVED)])
    svc, _ = service(gateway)
    steps = svc.sweep()
    assert gateway.calls == [("settle", UUID, 581200, "treasury"), ("redeem", UUID, "ldn")]
    assert [(s.action, s.display.kind) for s in steps] == [("settle", "done"), ("redeem", "done")]


def test_the_default_rate_is_used_when_the_date_has_none() -> None:
    gateway = FakeGateway([request(Status.APPROVED, date=20261019)])
    service(gateway)[0].sweep()
    assert gateway.calls[0] == ("settle", UUID, 580000, "treasury")


def test_a_settled_request_is_redeemed_and_not_settled_again() -> None:
    gateway = FakeGateway([request(Status.SETTLED)])
    service(gateway)[0].sweep()
    assert gateway.calls == [("redeem", UUID, "ldn")]


@pytest.mark.parametrize(
    "status", [Status.REQUESTED, Status.REJECTED, Status.REDEEMED, Status.NONE]
)
def test_other_states_need_nothing(status: Status) -> None:
    gateway = FakeGateway([request(status)])
    assert service(gateway)[0].sweep() == []
    assert gateway.calls == []


def test_a_missing_rate_keeps_the_request_approved_and_says_why() -> None:
    gateway = FakeGateway([request(Status.APPROVED)])
    svc, _ = service(gateway, Rates({}, None))
    assert svc.sweep() == []
    assert gateway.calls == []
    assert "no CADGBP rate for 2026-10-18" in svc.notes[RID]


def test_a_note_clears_once_the_rate_exists() -> None:
    gateway = FakeGateway([request(Status.APPROVED)])
    rates = [Rates({}, None)]
    svc = TreasuryService(gateway, lambda: rates[0], lambda _entry: None)
    svc.sweep()
    assert RID in svc.notes
    rates[0] = RATES
    svc.sweep()
    assert RID not in svc.notes
    assert [c[0] for c in gateway.calls] == ["settle", "redeem"]


def test_an_unreadable_rate_table_blocks_with_the_reason() -> None:
    gateway = FakeGateway([request(Status.APPROVED)])

    def broken() -> Rates:
        raise InvalidRate("fx-rates.json: not valid JSON")

    svc = TreasuryService(gateway, broken, lambda _entry: None)
    assert svc.sweep() == []
    assert "not valid JSON" in svc.notes[RID]


def test_an_amount_that_converts_to_nothing_is_blocked_before_sending() -> None:
    gateway = FakeGateway([request(Status.APPROVED, cad=1)])
    svc, _ = service(gateway)
    svc.sweep()
    assert gateway.calls == []
    assert "less than 0.01" in svc.notes[RID]


def test_a_pending_settle_is_reported_and_not_followed_by_a_redeem() -> None:
    gateway = FakeGateway([request(Status.APPROVED)])
    gateway.settle_outcome = Pending("op7", "tx7", "Pending")
    svc, _ = service(gateway)
    steps = svc.sweep()
    assert [c[0] for c in gateway.calls] == ["settle"]
    assert steps[0].display.kind == "pending"
    assert "op7" in svc.notes[RID]


def test_a_second_sweep_after_pending_asks_the_chain_again_with_the_same_key() -> None:
    gateway = FakeGateway([request(Status.APPROVED)])
    gateway.settle_outcome = Pending(None, "tx7", "already submitted")
    svc, _ = service(gateway)
    svc.sweep()
    svc.sweep()
    assert [c[0] for c in gateway.calls] == [
        "settle",
        "settle",
    ]  # the gateway's key makes it one write


def test_a_reverted_settle_is_noted_and_the_request_is_left_approved() -> None:
    gateway = FakeGateway([request(Status.APPROVED)])
    gateway.settle_outcome = ComplianceRevert("BadRate")
    svc, _ = service(gateway)
    steps = svc.sweep()
    assert [c[0] for c in gateway.calls] == ["settle"]
    assert steps[0].display.code == "BadRate"
    assert "FX rate" in svc.notes[RID]


def test_a_failed_redeem_is_noted_and_retried_on_the_next_sweep() -> None:
    gateway = FakeGateway([request(Status.SETTLED)])
    gateway.redeem_outcome = Failed("connector down", "op3")
    svc, _ = service(gateway)
    svc.sweep()
    assert "connector down" in svc.notes[RID]
    gateway.redeem_outcome = OK
    svc.sweep()
    assert RID not in svc.notes
    assert [c[0] for c in gateway.calls] == ["redeem", "redeem"]


def test_every_step_is_logged_with_the_request_action_operation_and_outcome() -> None:
    gateway = FakeGateway([request(Status.APPROVED)])
    svc, logs = service(gateway)
    svc.sweep()
    assert logs == [
        {"requestId": UUID, "action": "settle", "operationId": "op1", "outcome": "done"},
        {"requestId": UUID, "action": "redeem", "operationId": "op1", "outcome": "done"},
    ]


def test_an_id_this_app_did_not_make_is_skipped() -> None:
    foreign = request(Status.APPROVED, rid="0x" + "11" * 32)
    gateway = FakeGateway([foreign, request(Status.APPROVED)])
    svc, _ = service(gateway)
    svc.sweep()
    assert [c[1] for c in gateway.calls] == [UUID, UUID]


def test_one_request_failing_does_not_stop_the_others() -> None:
    other = "00000000-0000-0000-0000-000000000002"
    gateway = FakeGateway(
        [request(Status.APPROVED), request(Status.APPROVED, rid=request_id_from_uuid(other))]
    )
    gateway.settle_outcome = Failed("boom", None)
    service(gateway)[0].sweep()
    assert [c[1] for c in gateway.calls] == [UUID, other]
