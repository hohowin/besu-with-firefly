"""The treasury JSON API (adapter): routes a method and path to the gateway and shapes the answer.

No sockets here, so every route is tested by calling `handle`. `treasury_http.py` puts it on a
port. The API holds no keys: the signer is a wallet name and FireFly does the signing. Who may do
what is decided by the contract; the checks here only keep bad input from being sent.
"""

import re
import threading
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import Any, Protocol

from src.core.firefly.errors import FireflyError
from src.core.firefly.outcome import Outcome
from src.core.treasury.dates import processing_date
from src.core.treasury.errors import (
    InvalidAmount,
    InvalidRate,
    InvalidReason,
    LedgerMismatch,
    TreasuryError,
)
from src.core.treasury.fx import Rates
from src.core.treasury.gateway import Balances
from src.core.treasury.ids import request_id_from_uuid
from src.core.treasury.ledger import check_conservation
from src.core.treasury.messages import Display, describe
from src.core.treasury.money import parse_amount
from src.core.treasury.plan import NEW_WALLETS
from src.core.treasury.request import Action, Request, Status, validate_reason
from src.core.treasury.views import balances_view, fx_view, request_view

# Which HTTP status each contract revert gets: refused, wrong state, or bad input.
_REVERT_STATUS = {
    "NotRequester": 403,
    "NotApprover": 403,
    "SelfApproval": 403,
    "NotTreasury": 403,
    "NotBeneficiary": 403,
    "BadState": 409,
    "Exists": 409,
    "BadAmount": 400,
    "BadDate": 400,
    "BadRate": 400,
    "ReasonTooLong": 400,
}
_ERROR_CODES: dict[type[TreasuryError], str] = {
    InvalidAmount: "invalid_amount",
    InvalidReason: "invalid_reason",
    InvalidRate: "invalid_rate",
}
_REQUEST = re.compile(r"/api/requests/([0-9a-fA-F-]{36})(?:/(approve|reject|retry-settle))?")


class Gateway(Protocol):
    def create(
        self, request_uuid: str, amount: int, processing_date: int, signer: str
    ) -> Outcome: ...

    def approve(self, request_uuid: str, signer: str) -> Outcome: ...

    def reject(self, request_uuid: str, reason: str, signer: str) -> Outcome: ...

    def get_request(self, request_uuid: str) -> Request | None: ...

    def list_requests(self) -> list[Request]: ...

    def balances(self) -> Balances: ...


@dataclass(frozen=True)
class Response:
    status: int
    body: dict[str, Any]


class History:
    """The writes this app made, by request UUID. In memory: it is a convenience, the chain is the
    record."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def add(self, request_uuid: str, entry: dict[str, Any]) -> None:
        with self._lock:
            self._entries[request_uuid].append(entry)

    def of(self, request_uuid: str) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._entries[request_uuid])


class TreasuryApi:
    def __init__(
        self,
        gateway: Gateway,
        wallets: Mapping[str, str],
        load_rates: Callable[[], Rates],
        notes: Callable[[], Mapping[str, str]],
        trigger_sweep: Callable[[], None],
        history: History,
        clock: Callable[[], datetime],
        zone: tzinfo,
    ) -> None:
        self._gateway = gateway
        self._names = {address.lower(): name for name, address in wallets.items()}
        self._load_rates = load_rates
        self._notes = notes
        self._trigger_sweep = trigger_sweep
        self._history = history
        self._clock = clock
        self._zone = zone

    def handle(self, method: str, path: str, body: Mapping[str, Any] | None = None) -> Response:
        try:
            return self._route(method, path, body or {})
        except TreasuryError as error:
            return _error(400, _ERROR_CODES.get(type(error), "invalid_input"), str(error))
        except ValueError as error:
            return _error(400, "invalid_input", str(error))
        except FireflyError as error:
            return _error(502, "firefly_unavailable", str(error))

    def _route(self, method: str, path: str, body: Mapping[str, Any]) -> Response:
        if method == "GET":
            if path == "/api/requests":
                return self._list()
            if path == "/api/balances":
                return self._balances()
            if path == "/api/fx":
                return self._fx()
            found = _REQUEST.fullmatch(path)
            if found and found.group(2) is None:
                return self._one(found.group(1).lower())
        if method == "POST":
            if path == "/api/requests":
                return self._create(body)
            found = _REQUEST.fullmatch(path)
            if found and found.group(2):
                request_uuid, action = found.group(1).lower(), found.group(2)
                if action == "approve":
                    return self._approve(request_uuid, body)
                if action == "reject":
                    return self._reject(request_uuid, body)
                return self._retry_settle(request_uuid)
        return _error(404, "not_found", f"no route for {method} {path}")

    # ---- writes ----

    def _create(self, body: Mapping[str, Any]) -> Response:
        signer = self._signer(body)
        amount_text = body.get("amount")
        if not isinstance(amount_text, str):
            raise InvalidAmount("the amount must be text such as '1000.00'")
        amount = parse_amount(amount_text)
        request_uuid = _uuid(body.get("id"))
        date = processing_date(self._clock(), self._zone)
        outcome = self._gateway.create(request_uuid, amount, date, signer)
        return self._written(request_uuid, Action.CREATE, outcome)

    def _approve(self, request_uuid: str, body: Mapping[str, Any]) -> Response:
        outcome = self._gateway.approve(request_uuid, self._signer(body))
        response = self._written(request_uuid, Action.APPROVE, outcome)
        if response.body["status"] == "done":
            self._trigger_sweep()  # steps 5 to 7 follow on their own
        return response

    def _reject(self, request_uuid: str, body: Mapping[str, Any]) -> Response:
        signer = self._signer(body)
        reason = validate_reason(str(body.get("reason", "")))
        outcome = self._gateway.reject(request_uuid, reason, signer)
        return self._written(request_uuid, Action.REJECT, outcome)

    def _retry_settle(self, request_uuid: str) -> Response:
        request = self._gateway.get_request(request_uuid)
        if request is None:
            return _error(404, "not_found", "no such request")
        if request.status is not Status.APPROVED:
            return _error(409, "BadState", "only an approved request can be settled")
        self._trigger_sweep()
        return Response(202, {"status": "accepted", "message": "Settlement started."})

    def _signer(self, body: Mapping[str, Any]) -> str:
        signer = body.get("as")
        if not isinstance(signer, str) or signer not in NEW_WALLETS:
            raise ValueError(f"'as' must be one of {', '.join(NEW_WALLETS)}")
        return signer

    def _written(self, request_uuid: str, action: Action, outcome: Outcome) -> Response:
        display = describe(outcome, action)
        self._history.add(
            request_uuid,
            {
                "action": action.value,
                "outcome": display.kind,
                "operationId": display.operation_id,
                "message": display.message,
                "at": self._clock().isoformat(),
            },
        )
        return _from_display(request_uuid, display)

    # ---- reads ----

    def _view(self, request: Request) -> dict[str, Any]:
        return request_view(request, self._names, self._notes().get(request.id))

    def _list(self) -> Response:
        views = [self._view(r) for r in self._gateway.list_requests()]
        return Response(200, {"requests": list(reversed(views))})

    def _one(self, request_uuid: str) -> Response:
        request = self._gateway.get_request(request_uuid)
        if request is None:
            return _error(404, "not_found", "no such request")
        view = self._view(request)
        view["steps"] = self._history.of(request_uuid)
        return Response(200, view)

    def _balances(self) -> Response:
        held = self._gateway.balances()
        body = balances_view(held)
        try:
            check_conservation(
                self._gateway.list_requests(), held.supply["cadc"], held.supply["gbpc"]
            )
            body["conserved"] = True
            body["problem"] = None
        except LedgerMismatch as error:
            body["conserved"] = False
            body["problem"] = str(error)
        return Response(200, body)

    def _fx(self) -> Response:
        try:
            rates = self._load_rates()
        except TreasuryError as error:
            return _error(422, "fx_table_invalid", str(error))
        return Response(200, fx_view(rates, processing_date(self._clock(), self._zone)))


def _uuid(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("'id' must be the UUID the form made")
    request_id_from_uuid(value)  # raises ValueError if it is not a UUID
    return value.strip().lower()


def _from_display(request_uuid: str, display: Display) -> Response:
    base = {"id": request_uuid, "message": display.message, "operationId": display.operation_id}
    if display.kind in ("done", "pending"):
        return Response(202, {**base, "status": display.kind})
    if display.kind == "reverted":
        status = _REVERT_STATUS.get(display.code or "", 409)
        return Response(status, {**base, "status": "refused", "error": display.code})
    return Response(502, {**base, "status": "failed", "error": "write_failed"})


def _error(status: int, code: str, message: str) -> Response:
    return Response(status, {"status": "error", "error": code, "message": message})
