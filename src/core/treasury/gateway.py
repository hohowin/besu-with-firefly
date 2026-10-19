"""The treasury calls on FireFly (pure orchestration over the port): who signs which write, with
which input and idempotency key, and how a read becomes a `Request`.

Writes return an `Outcome`; only `Succeeded` is success. A repeated write (same idempotency key)
is `Pending`, never a second write: the chain state, read back, says what really happened.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.core.firefly.errors import AlreadySubmitted, FireflyError
from src.core.firefly.outcome import Outcome, Pending, classify_error, classify_operation
from src.core.firefly.port import ContractApiPort
from src.core.treasury.ids import idempotency_key, request_id_from_uuid
from src.core.treasury.plan import NEW_WALLETS
from src.core.treasury.request import Action, Request, Status

API = "funding-request"
CADC = "cadc"
GBPC = "gbpc"
_FIELDS = ("requester", "processingDate", "status", "amountCad", "amountGbp", "ratePpm", "approver")
_ZERO_ADDRESS = "0x" + "00" * 20


@dataclass(frozen=True)
class Balances:
    balances: dict[str, dict[str, int]]  # wallet name to {"cadc": n, "gbpc": n}
    supply: dict[str, int]  # {"cadc": n, "gbpc": n}


class TreasuryGateway:
    def __init__(
        self, port: ContractApiPort, wallets: Mapping[str, str], timeout: float = 120.0
    ) -> None:
        self._port = port
        self._wallets = dict(wallets)
        self._timeout = timeout

    # ---- writes ----

    def create(self, request_uuid: str, amount: int, processing_date: int, signer: str) -> Outcome:
        inputs = {
            "id": request_id_from_uuid(request_uuid),
            "amountCad": str(amount),
            "processingDate": str(processing_date),
        }
        return self._write("createRequest", inputs, signer, request_uuid, Action.CREATE)

    def approve(self, request_uuid: str, signer: str) -> Outcome:
        inputs = {"id": request_id_from_uuid(request_uuid)}
        return self._write("approve", inputs, signer, request_uuid, Action.APPROVE)

    def reject(self, request_uuid: str, reason: str, signer: str) -> Outcome:
        inputs = {"id": request_id_from_uuid(request_uuid), "reason": reason}
        return self._write("reject", inputs, signer, request_uuid, Action.REJECT)

    def settle(self, request_uuid: str, rate_ppm: int, signer: str) -> Outcome:
        inputs = {"id": request_id_from_uuid(request_uuid), "ratePpm": str(rate_ppm)}
        return self._write("settle", inputs, signer, request_uuid, Action.SETTLE)

    def redeem(self, request_uuid: str, signer: str) -> Outcome:
        inputs = {"id": request_id_from_uuid(request_uuid)}
        return self._write("redeem", inputs, signer, request_uuid, Action.REDEEM)

    def _write(
        self, method: str, inputs: dict[str, str], signer: str, request_uuid: str, action: Action
    ) -> Outcome:
        if signer not in self._wallets:
            raise ValueError(f"unknown signer {signer!r}")
        try:
            return classify_operation(
                self._port.api_invoke(
                    API,
                    method,
                    inputs,
                    key=self._wallets[signer],
                    idempotency_key=idempotency_key(request_uuid, action),
                    timeout=self._timeout,
                )
            )
        except AlreadySubmitted as earlier:
            return Pending(None, earlier.transaction_id, "already submitted")
        except FireflyError as error:
            return classify_error(error)

    # ---- reads (the chain is the source of truth) ----

    def get_request(self, request_uuid: str) -> Request | None:
        request_id = request_id_from_uuid(request_uuid)
        return parse_request(
            request_id, self._port.api_query(API, "getRequest", {"id": request_id})
        )

    def list_requests(self) -> list[Request]:
        count = int(self._port.api_query(API, "requestCount", {}))
        found: list[Request] = []
        for index in range(count):
            request_id = str(self._port.api_query(API, "requestIdAt", {"index": str(index)}))
            request = parse_request(
                request_id, self._port.api_query(API, "getRequest", {"id": request_id})
            )
            if request is not None:
                found.append(request)
        return found

    def balances(self) -> Balances:
        names = [name for name in NEW_WALLETS if name in self._wallets]
        balances = {
            name: {
                token: int(
                    self._port.api_query(token, "balanceOf", {"account": self._wallets[name]})
                )
                for token in (CADC, GBPC)
            }
            for name in names
        }
        supply = {
            token: int(self._port.api_query(token, "totalSupply", {})) for token in (CADC, GBPC)
        }
        return Balances(balances, supply)


def parse_request(request_id: str, raw: Any) -> Request | None:
    """A `getRequest` answer to a `Request`, or None when no such request exists.

    FireFly returns the struct as an object by field name; a single wrapper key or a plain list
    in field order are accepted too, because only a live stack settles which one it is.
    """
    fields = _fields(raw)
    status = Status(int(fields["status"]))
    if status is Status.NONE:
        return None
    approver = str(fields["approver"]).lower()
    return Request(
        id=request_id,
        requester=str(fields["requester"]).lower(),
        amount_cad=int(fields["amountCad"]),
        processing_date=int(fields["processingDate"]),
        status=status,
        amount_gbp=int(fields["amountGbp"]),
        rate_ppm=int(fields["ratePpm"]),
        approver=None if approver == _ZERO_ADDRESS else approver,
    )


def _fields(raw: Any) -> Mapping[str, Any]:
    if isinstance(raw, Mapping):
        if "requester" in raw:
            return raw
        if len(raw) == 1:
            return _fields(next(iter(raw.values())))
    if isinstance(raw, Sequence) and not isinstance(raw, str) and len(raw) == len(_FIELDS):
        return dict(zip(_FIELDS, raw, strict=True))
    raise ValueError(f"cannot read a funding request from {raw!r}")
