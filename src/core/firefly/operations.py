"""FireFly request bodies and response reading (pure, no I/O).

Shapes follow the Phase 0 spike (`docs/spike-results.md`, Risks 1 and 7): a deploy or invoke with
`?confirm=true` returns the final operation, and a repeated `idempotencyKey` returns HTTP 409
with `FF10431` and the original transaction id.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

SUCCEEDED = "Succeeded"
FAILED = "Failed"

_IDEMPOTENCY_CONFLICT = re.compile(r"FF10431\b.*?transaction '([^']+)'")


@dataclass(frozen=True)
class Operation:
    id: str
    status: str
    tx: str | None = None
    error: str | None = None
    output: Mapping[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == SUCCEEDED

    @property
    def failed(self) -> bool:
        return self.status == FAILED


def parse_operation(body: Any) -> Operation:
    """Read a FireFly operation. Raises ValueError for anything that is not one."""
    if not isinstance(body, Mapping) or "id" not in body or "status" not in body:
        raise ValueError(f"not a FireFly operation: {body!r}")
    output = body.get("output")
    return Operation(
        id=str(body["id"]),
        status=str(body["status"]),
        tx=str(body["tx"]) if body.get("tx") else None,
        error=str(body["error"]) if body.get("error") else None,
        output=output if isinstance(output, Mapping) else {},
    )


def deploy_body(
    bytecode: str,
    abi: Sequence[Any],
    constructor_input: Sequence[Any],
    key: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "contract": bytecode,
        "definition": list(abi),
        "input": list(constructor_input),
    }
    return _with_signer(body, key, idempotency_key)


def invoke_body(
    address: str,
    method: Mapping[str, Any],
    inputs: Mapping[str, Any],
    key: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"location": {"address": address}, "method": method, "input": inputs}
    return _with_signer(body, key, idempotency_key)


def query_body(
    address: str, method: Mapping[str, Any], inputs: Mapping[str, Any]
) -> dict[str, Any]:
    """A read: no signer, so no key and no idempotency key."""
    return {"location": {"address": address}, "method": method, "input": inputs}


def api_query_body(inputs: Mapping[str, Any]) -> dict[str, Any]:
    """A read through a registered contract API: arguments by parameter name."""
    return {"input": dict(inputs)}


def api_invoke_body(
    inputs: Mapping[str, Any], key: str | None = None, idempotency_key: str | None = None
) -> dict[str, Any]:
    """A write through a registered contract API."""
    return _with_signer({"input": dict(inputs)}, key, idempotency_key)


def _with_signer(
    body: dict[str, Any], key: str | None, idempotency_key: str | None
) -> dict[str, Any]:
    if key:
        body["key"] = key
    if idempotency_key:
        body["idempotencyKey"] = idempotency_key
    return body


def already_submitted_transaction(status: int, body: Any) -> str | None:
    """The original transaction id if this is a 409 `FF10431` (idempotency key already used)."""
    if status != 409:
        return None
    text = body.get("error", "") if isinstance(body, Mapping) else str(body)
    match = _IDEMPOTENCY_CONFLICT.search(str(text))
    return match.group(1) if match else None


def find_method(interface: Mapping[str, Any], name: str) -> dict[str, Any]:
    """The method called `name` in a FireFly contract interface (as `generate` returns it)."""
    for method in interface.get("methods", []):
        if method.get("name") == name:
            return dict(method)
    raise ValueError(f"the interface has no method {name!r}")


_TRANSIENT = (
    "context deadline exceeded",
    "client.timeout",
    "timed out",
    "connection refused",
    "connection reset",
    "could not reach firefly",
    "http 502",
    "http 503",
    "http 504",
)


def is_transient(message: str) -> bool:
    """True for a failure that says nothing about the request itself (a timeout, a dropped
    connection), so sending the same request again is reasonable. A revert is not transient."""
    text = message.lower()
    return any(marker in text for marker in _TRANSIENT)
