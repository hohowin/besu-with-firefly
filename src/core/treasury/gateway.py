"""The treasury calls on FireFly (pure orchestration over the port): who signs which write, with
which input and idempotency key, and how a read becomes a `Request`.

Writes return an `Outcome`; only `Succeeded` is success. A repeated write (same idempotency key)
whose first try succeeded or is still running is `Pending`, never a second write: the chain state,
read back, says what really happened. If the first try **failed** (a refusal by the contract, a
connector error), FireFly still keeps its key, so the same key can never succeed. The write is then
sent again under a new key that is the same every time for the same failed transaction.

What "failed" looks like (seen on a live stack): a write the contract refuses is stopped while the
gas is estimated, so its operation stays `Initialized` and never becomes `Failed`. `Initialized`
means it never reached the connector. An operation that is `Pending` or `Succeeded` is not sent
again. (A duplicate click inside the few milliseconds when a good first try is still `Initialized`
is possible; the contract then refuses the second one, e.g. `BadState`, so nothing is done twice.)
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from src.core.firefly.errors import AlreadySubmitted, FireflyError
from src.core.firefly.operations import Operation
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
_NEVER_SENT = {"Failed", "Initialized"}  # operation states of a try that did not go through
_MAX_RETRIES = 5  # new keys tried after failed earlier tries, so a broken key cannot loop forever


class WritePort(ContractApiPort, Protocol):
    def transaction_operations(self, transaction_id: str) -> list[Operation]: ...


@dataclass(frozen=True)
class Balances:
    balances: dict[str, dict[str, int]]  # wallet name to {"cadc": n, "gbpc": n}
    supply: dict[str, int]  # {"cadc": n, "gbpc": n}


class TreasuryGateway:
    def __init__(self, port: WritePort, wallets: Mapping[str, str], timeout: float = 120.0) -> None:
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
        key = idempotency_key(request_uuid, action)
        last: Outcome = Pending(None, None, "already submitted")
        for _ in range(_MAX_RETRIES + 1):
            try:
                return classify_operation(
                    self._port.api_invoke(
                        API,
                        method,
                        inputs,
                        key=self._wallets[signer],
                        idempotency_key=key,
                        timeout=self._timeout,
                    )
                )
            except AlreadySubmitted as earlier:
                last = Pending(None, earlier.transaction_id, "already submitted")
                try:
                    operations = self._port.transaction_operations(earlier.transaction_id)
                except FireflyError as error:
                    return classify_error(error)
                if not operations or not all(op.status in _NEVER_SENT for op in operations):
                    return last  # it worked once or is still running: do not send it again
                key = f"{key}-after-{earlier.transaction_id[:8]}"
            except FireflyError as error:
                return classify_error(error)
        return last

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
