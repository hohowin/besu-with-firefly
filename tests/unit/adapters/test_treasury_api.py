from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from src.adapters.treasury_api import History, Response, TreasuryApi
from src.core.firefly.errors import FireflyError
from src.core.firefly.operations import Operation
from src.core.firefly.outcome import ComplianceRevert, Failed, Outcome, Pending, Succeeded
from src.core.treasury.errors import InvalidRate
from src.core.treasury.fx import Rates
from src.core.treasury.gateway import Balances
from src.core.treasury.ids import request_id_from_uuid
from src.core.treasury.request import Request, Status

UUID = "123e4567-e89b-12d3-a456-426614174000"
RID = request_id_from_uuid(UUID)
WALLETS = {"ldn": "0xa1", "tor": "0xa2", "treasury": "0xa3", "admin": "0xff"}
NOW = datetime(2026, 10, 18, 22, 30, tzinfo=UTC)  # 23:30 in London: still the 18th
OK = Succeeded(Operation("op1", "Succeeded", tx="tx1"))


def stored(status: Status = Status.REQUESTED) -> Request:
    settled = status in (Status.SETTLED, Status.REDEEMED)
    return Request(
        RID, "0xa1", 100000, 20261018, status, 58000 if settled else 0, 580000 if settled else 0
    )


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.outcome: Outcome = OK
        self.requests: list[Request] = []
        self.supply = {"cadc": 0, "gbpc": 0}
        self.error: Exception | None = None

    def _done(self, *call: Any) -> Outcome:
        self.calls.append(call)
        return self.outcome

    def create(self, request_uuid: str, amount: int, processing_date: int, signer: str) -> Outcome:
        return self._done("create", request_uuid, amount, processing_date, signer)

    def approve(self, request_uuid: str, signer: str) -> Outcome:
        return self._done("approve", request_uuid, signer)

    def reject(self, request_uuid: str, reason: str, signer: str) -> Outcome:
        return self._done("reject", request_uuid, reason, signer)

    def get_request(self, request_uuid: str) -> Request | None:
        if self.error:
            raise self.error
        return self.requests[0] if self.requests else None

    def list_requests(self) -> list[Request]:
        return self.requests

    def balances(self) -> Balances:
        held = {"ldn": {"cadc": 0, "gbpc": 0}, "treasury": {"cadc": 0, "gbpc": 0}}
        return Balances(held, self.supply)


class Harness:
    def __init__(self) -> None:
        self.gateway = FakeGateway()
        self.sweeps = 0
        self.notes: dict[str, str] = {}
        self.rates = Rates({}, 580000)
        self.rates_error: Exception | None = None
        self.history = History()
        self.api = TreasuryApi(
            self.gateway,
            WALLETS,
            self._rates,
            lambda: self.notes,
            self._sweep,
            self.history,
            lambda: NOW,
            ZoneInfo("Europe/London"),
        )

    def _rates(self) -> Rates:
        if self.rates_error:
            raise self.rates_error
        return self.rates

    def _sweep(self) -> None:
        self.sweeps += 1

    def post(self, path: str, body: dict[str, Any]) -> Response:
        return self.api.handle("POST", path, body)

    def get(self, path: str) -> Response:
        return self.api.handle("GET", path)


@pytest.fixture
def h() -> Harness:
    return Harness()


# ---- create ----


def test_create_sends_the_amount_in_minor_units_and_londons_date(h: Harness) -> None:
    response = h.post("/api/requests", {"as": "ldn", "amount": "1000.00", "id": UUID})
    assert response.status == 202
    assert response.body["status"] == "done"
    assert h.gateway.calls == [("create", UUID, 100000, 20261018, "ldn")]


def test_the_processing_date_is_the_requesters_local_date_not_utc(h: Harness) -> None:
    h.post("/api/requests", {"as": "ldn", "amount": "1.00", "id": UUID})
    assert h.gateway.calls[0][3] == 20261018  # 22:30 UTC on the 18th is 23:30 in London


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"as": "ldn", "amount": "0", "id": UUID}, "invalid_amount"),
        ({"as": "ldn", "amount": "-5", "id": UUID}, "invalid_amount"),
        ({"as": "ldn", "amount": "1000.001", "id": UUID}, "invalid_amount"),
        ({"as": "ldn", "amount": "9999999.00", "id": UUID}, "invalid_amount"),
        ({"as": "ldn", "amount": 1000, "id": UUID}, "invalid_amount"),
        ({"as": "ldn", "amount": "1.00"}, "invalid_input"),
        ({"as": "ldn", "amount": "1.00", "id": "nope"}, "invalid_input"),
        ({"as": "admin", "amount": "1.00", "id": UUID}, "invalid_input"),
        ({"amount": "1.00", "id": UUID}, "invalid_input"),
    ],
)
def test_bad_input_is_400_and_nothing_is_sent(h: Harness, body: dict[str, Any], code: str) -> None:
    response = h.post("/api/requests", body)
    assert response.status == 400
    assert response.body["error"] == code
    assert h.gateway.calls == []


# ---- the outcome of a write ----


def test_a_pending_write_is_202_pending_never_done(h: Harness) -> None:
    h.gateway.outcome = Pending("op7", "tx7", "Pending")
    response = h.post("/api/requests", {"as": "ldn", "amount": "1.00", "id": UUID})
    assert (response.status, response.body["status"]) == (202, "pending")
    assert response.body["operationId"] == "op7"


@pytest.mark.parametrize(
    ("code", "status"),
    [("SelfApproval", 403), ("NotApprover", 403), ("BadState", 409), ("BadRate", 400)],
)
def test_a_revert_maps_to_its_http_status(h: Harness, code: str, status: int) -> None:
    h.gateway.outcome = ComplianceRevert(code)
    response = h.post(f"/api/requests/{UUID}/approve", {"as": "ldn"})
    assert response.status == status
    assert response.body["error"] == code
    assert h.sweeps == 0


def test_a_failed_write_is_502(h: Harness) -> None:
    h.gateway.outcome = Failed("connector down", "op9")
    response = h.post(f"/api/requests/{UUID}/approve", {"as": "tor"})
    assert (response.status, response.body["error"]) == (502, "write_failed")


# ---- approve, reject, retry ----


def test_a_successful_approve_starts_the_treasury_steps(h: Harness) -> None:
    response = h.post(f"/api/requests/{UUID}/approve", {"as": "tor"})
    assert response.status == 202
    assert h.gateway.calls == [("approve", UUID, "tor")]
    assert h.sweeps == 1


def test_a_pending_approve_does_not_start_them(h: Harness) -> None:
    h.gateway.outcome = Pending("op1", None, "Pending")
    h.post(f"/api/requests/{UUID}/approve", {"as": "tor"})
    assert h.sweeps == 0


def test_reject_needs_a_reason_of_at_most_140_characters(h: Harness) -> None:
    ok = h.post(f"/api/requests/{UUID}/reject", {"as": "tor", "reason": "  over budget "})
    assert ok.status == 202
    assert h.gateway.calls == [("reject", UUID, "over budget", "tor")]
    for reason in ("", "   ", "x" * 141):
        bad = h.post(f"/api/requests/{UUID}/reject", {"as": "tor", "reason": reason})
        assert (bad.status, bad.body["error"]) == (400, "invalid_reason")
    assert len(h.gateway.calls) == 1


def test_retry_settle_only_for_an_approved_request(h: Harness) -> None:
    assert h.post(f"/api/requests/{UUID}/retry-settle", {}).status == 404
    h.gateway.requests = [stored(Status.REQUESTED)]
    assert h.post(f"/api/requests/{UUID}/retry-settle", {}).status == 409
    assert h.sweeps == 0
    h.gateway.requests = [stored(Status.APPROVED)]
    assert h.post(f"/api/requests/{UUID}/retry-settle", {}).status == 202
    assert h.sweeps == 1


def test_the_uuid_in_the_path_is_case_insensitive(h: Harness) -> None:
    h.post(f"/api/requests/{UUID.upper()}/approve", {"as": "tor"})
    assert h.gateway.calls[0][1] == UUID


# ---- reads ----


def test_list_shows_newest_first_with_names_amounts_and_notes(h: Harness) -> None:
    other = request_id_from_uuid("00000000-0000-0000-0000-000000000002")
    first = stored(Status.APPROVED)
    second = Request(other, "0xa1", 500, 20261018, Status.REQUESTED)
    h.gateway.requests = [first, second]
    h.notes = {RID: "FX rate missing"}
    body = h.get("/api/requests").body["requests"]
    assert [r["id"] for r in body] == ["00000000-0000-0000-0000-000000000002", UUID]
    assert body[1]["requester"] == "ldn"
    assert body[1]["amountCad"] == "1000.00"
    assert body[1]["note"] == "FX rate missing"
    assert body[0]["note"] is None


def test_one_request_includes_the_writes_this_app_made(h: Harness) -> None:
    h.gateway.requests = [stored(Status.APPROVED)]
    h.post(f"/api/requests/{UUID}/approve", {"as": "tor"})
    body = h.get(f"/api/requests/{UUID}").body
    assert body["status"] == "approved"
    assert [(s["action"], s["outcome"], s["operationId"]) for s in body["steps"]] == [
        ("approve", "done", "op1")
    ]


def test_an_unknown_request_is_404(h: Harness) -> None:
    assert h.get(f"/api/requests/{UUID}").status == 404


def test_balances_report_conservation(h: Harness) -> None:
    h.gateway.requests = [stored(Status.APPROVED)]
    h.gateway.supply = {"cadc": 100000, "gbpc": 0}
    body = h.get("/api/balances").body
    assert body["conserved"] is True and body["problem"] is None
    assert body["supply"] == {"cadc": "1000.00", "gbpc": "0.00"}


def test_balances_say_so_when_the_books_do_not_balance(h: Harness) -> None:
    h.gateway.requests = [stored(Status.APPROVED)]
    h.gateway.supply = {"cadc": 99999, "gbpc": 0}
    body = h.get("/api/balances").body
    assert body["conserved"] is False
    assert "CADC supply is 99999" in body["problem"]


def test_fx_shows_the_table_and_todays_rate(h: Harness) -> None:
    body = h.get("/api/fx").body
    assert body["default"] == "0.580000"
    assert body["today"] == {"date": "2026-10-18", "rate": "0.580000", "source": "default"}


def test_an_invalid_fx_table_is_422_with_the_reason(h: Harness) -> None:
    h.rates_error = InvalidRate("fx-rates.json: not valid JSON")
    response = h.get("/api/fx")
    assert (response.status, response.body["error"]) == (422, "fx_table_invalid")
    assert "not valid JSON" in response.body["message"]


# ---- failures and routes ----


def test_firefly_being_down_is_502(h: Harness) -> None:
    h.gateway.error = FireflyError("connection refused")
    response = h.get(f"/api/requests/{UUID}")
    assert (response.status, response.body["error"]) == (502, "firefly_unavailable")


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/nope"), ("DELETE", "/api/requests"), ("POST", "/api/balances"),
     ("GET", f"/api/requests/{UUID}/approve")],
)  # fmt: skip
def test_unknown_routes_are_404(h: Harness, method: str, path: str) -> None:
    assert h.api.handle(method, path).status == 404


def test_no_response_carries_a_key_or_password(h: Harness) -> None:
    h.gateway.requests = [stored(Status.SETTLED)]
    for path in ("/api/requests", f"/api/requests/{UUID}", "/api/balances", "/api/fx"):
        text = str(h.get(path).body).lower()
        assert "privatekey" not in text and "password" not in text
