"""The treasury service (steps 5 to 7): settle what is approved, redeem what is settled.

It works from the state it reads back from the chain, never from what it did last time, so it is
right after a crash and a repeat sends nothing twice (the gateway's idempotency key). Where the
rate table is read from, and where log lines go, are passed in: this module does no I/O.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from src.core.firefly.outcome import Outcome
from src.core.treasury.errors import TreasuryError
from src.core.treasury.fx import Rates, convert_cad_to_gbp, lookup
from src.core.treasury.ids import uuid_from_request_id
from src.core.treasury.messages import Display, describe
from src.core.treasury.request import Action, Request, Status

TREASURY_SIGNER = "treasury"
BENEFICIARY_SIGNER = "ldn"


class Writes(Protocol):
    def list_requests(self) -> list[Request]: ...

    def settle(self, request_uuid: str, rate_ppm: int, signer: str) -> Outcome: ...

    def redeem(self, request_uuid: str, signer: str) -> Outcome: ...


@dataclass(frozen=True)
class Step:
    request_id: str  # the UUID
    action: str
    display: Display


class TreasuryService:
    def __init__(
        self,
        gateway: Writes,
        load_rates: Callable[[], Rates],
        log: Callable[[dict[str, Any]], None],
    ) -> None:
        self._gateway = gateway
        self._load_rates = load_rates
        self._log = log
        self._lock = threading.Lock()
        # Why a request is waiting, by its `0x` id. In memory only: the next sweep recomputes it.
        self.notes: dict[str, str] = {}

    def sweep(self) -> list[Step]:
        """One pass over every request. Returns the writes it attempted, in order."""
        with self._lock:
            steps: list[Step] = []
            for request in self._gateway.list_requests():
                if request.status is Status.APPROVED:
                    steps.extend(self._settle_then_redeem(request))
                elif request.status is Status.SETTLED:
                    steps.extend(self._redeem(request))
                else:
                    self.notes.pop(request.id, None)
            return steps

    def _settle_then_redeem(self, request: Request) -> list[Step]:
        try:
            request_uuid = uuid_from_request_id(request.id)
        except ValueError:
            return []
        try:
            rate_ppm, _source = lookup(self._load_rates(), request.processing_date)
            convert_cad_to_gbp(request.amount_cad, rate_ppm)  # refuse a zero result before sending
        except TreasuryError as error:
            self.notes[request.id] = str(error)
            return []
        step = self._act(
            request,
            request_uuid,
            Action.SETTLE,
            self._gateway.settle(request_uuid, rate_ppm, TREASURY_SIGNER),
        )
        if step.display.kind != "done":
            return [step]
        return [step, *self._redeem(request)]

    def _redeem(self, request: Request) -> list[Step]:
        try:
            request_uuid = uuid_from_request_id(request.id)
        except ValueError:
            return []
        outcome = self._gateway.redeem(request_uuid, BENEFICIARY_SIGNER)
        return [self._act(request, request_uuid, Action.REDEEM, outcome)]

    def _act(self, request: Request, request_uuid: str, action: Action, outcome: Outcome) -> Step:
        display = describe(outcome, action)
        if display.kind == "done":
            self.notes.pop(request.id, None)
        else:
            self.notes[request.id] = display.message
        self._log(
            {
                "requestId": request_uuid,
                "action": action.value,
                "operationId": display.operation_id,
                "outcome": display.kind,
            }
        )
        return Step(request_uuid, action.value, display)
