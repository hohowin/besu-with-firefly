"""FireFly HTTP client (adapter, standard library only).

The transport is injected, so the client is tested without Docker. Writes use `?confirm=true`,
so FireFly answers with the final operation; a still-pending operation is polled with a bound.
"""

import json
import os
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.adapters.settings import service_url
from src.core.firefly.errors import (
    AlreadySubmitted,
    FireflyError,
    OperationFailed,
    OperationTimeout,
    Reverted,
    WriteUnconfirmed,
)
from src.core.firefly.operations import (
    Operation,
    TxEvent,
    already_submitted_transaction,
    api_invoke_body,
    api_query_body,
    deploy_body,
    invoke_body,
    is_transient,
    parse_events,
    parse_operation,
    query_body,
    revert_reason,
)

__all__ = [
    "AlreadySubmitted",
    "DeployResult",
    "FireflyClient",
    "FireflyError",
    "OperationFailed",
    "OperationTimeout",
    "Reverted",
    "Transport",
    "firefly_url",
    "WriteUnconfirmed",
    "http_transport",
]

READ_RETRIES = 3

# (HTTP method, path, JSON body or None) -> (HTTP status, parsed JSON or text).
Transport = Callable[[str, str, Any], tuple[int, Any]]


@dataclass(frozen=True)
class DeployResult:
    address: str
    operation: Operation


def firefly_url(env: Mapping[str, str] = os.environ) -> str:
    """FireFly's address: `FIREFLY_URL`, or `http://localhost:5000` when it is not set."""
    return service_url("FIREFLY_URL", "http://localhost:5000", env)


def http_transport(base_url: str | None = None, timeout: float = 150.0) -> Transport:
    """A transport over `urllib`. The long timeout covers `confirm=true`, which blocks.

    Without `base_url` the address comes from `FIREFLY_URL` (see `firefly_url`).
    """
    base_url = base_url or firefly_url()

    def send(method: str, path: str, body: Any = None) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"{base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return response.status, _decode(response.read())
        except urllib.error.HTTPError as error:
            return error.code, _decode(error.read())

    return send


def _decode(raw: bytes) -> Any:
    text = raw.decode("utf-8", errors="replace")
    try:
        return json.loads(text) if text else None
    except json.JSONDecodeError:
        return text


def _may_have_been_sent(cause: BaseException | None) -> bool:
    """False when the request certainly never left (connection refused, name not found)."""
    reason = getattr(cause, "reason", cause)  # a URLError wraps the real error as `reason`
    return isinstance(cause, OSError) and not isinstance(
        reason, ConnectionRefusedError | socket.gaierror
    )


class FireflyClient:
    def __init__(
        self,
        transport: Transport,
        namespace: str = "default",
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._send = transport
        self._ns = f"/api/v1/namespaces/{namespace}"
        self._sleep = sleep
        self._clock = clock

    def status(self) -> dict[str, Any]:
        return dict(self._read("GET", "/api/v1/status"))

    def deploy(
        self,
        bytecode: str,
        abi: Sequence[Any],
        constructor_input: Sequence[Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = 120.0,
    ) -> DeployResult:
        body = deploy_body(bytecode, abi, constructor_input, key, idempotency_key)
        operation = self._write("/contracts/deploy?confirm=true", body, timeout)
        location = operation.output.get("contractLocation")
        address = location.get("address") if isinstance(location, Mapping) else None
        if not address:
            raise FireflyError(f"deploy operation {operation.id} returned no contract address")
        return DeployResult(str(address), operation)

    def invoke(
        self,
        address: str,
        method: Mapping[str, Any],
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = 120.0,
    ) -> Operation:
        body = invoke_body(address, method, inputs, key, idempotency_key)
        return self._write("/contracts/invoke?confirm=true", body, timeout)

    def query(
        self, address: str, method: Mapping[str, Any], inputs: Mapping[str, Any]
    ) -> Any:
        body = query_body(address, method, inputs)
        return self._read("POST", f"{self._ns}/contracts/query", body)

    def generate_interface(self, abi: Sequence[Any]) -> dict[str, Any]:
        """Ask FireFly to turn an ABI into a contract interface (FFI). Nothing is registered."""
        return dict(
            self._read(
                "POST",
                f"{self._ns}/contracts/interfaces/generate",
                {"input": {"abi": list(abi)}},
            )
        )

    def ensure_interface(self, name: str, version: str, abi: Sequence[Any]) -> str:
        """The id of the contract interface `name`/`version`, registering it from the ABI if it
        does not exist yet. (FireFly answers a repeated registration with 409, so look first.)"""
        found = self._list(f"/contracts/interfaces?name={name}&version={version}")
        if found:
            return str(found[0]["id"])
        generated = self._read(
            "POST",
            f"{self._ns}/contracts/interfaces/generate",
            {"name": name, "version": version, "input": {"abi": list(abi)}},
        )
        status, registered = self._call(
            "POST", f"{self._ns}/contracts/interfaces?confirm=true", generated
        )
        self._raise_for(status, registered)
        return str(registered["id"])

    def api_registered(self, name: str) -> bool:
        """Whether a contract API called `name` exists."""
        return bool(self._list(f"/apis?name={name}"))

    def ensure_api(self, name: str, interface_id: str, address: str) -> str:
        """The id of the contract API `name` for this interface and address, created if missing.

        An API of that name that points somewhere else is an error, not silently reused.
        """
        found = self._list(f"/apis?name={name}")
        if found:
            api = found[0]
            same_interface = api.get("interface", {}).get("id") == interface_id
            known = str(api.get("location", {}).get("address", "")).lower()
            same_address = known == address.lower()
            if not (same_interface and same_address):
                raise FireflyError(
                    f"API '{name}' already exists for another interface or address. "
                    "Run `python scripts/stack.py reset` to start from a clean stack."
                )
            return str(api["id"])
        body = {"name": name, "interface": {"id": interface_id}, "location": {"address": address}}
        status, created = self._call("POST", f"{self._ns}/apis?confirm=true", body)
        self._raise_for(status, created)
        return str(created["id"])

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        """Read through a registered contract API and return the output value."""
        body = self._read("POST", f"{self._ns}/apis/{api}/query/{method}", api_query_body(inputs))
        return body.get("output") if isinstance(body, Mapping) else body

    def api_invoke(
        self,
        api: str,
        method: str,
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = 120.0,
    ) -> Operation:
        body = api_invoke_body(inputs, key, idempotency_key)
        return self._write(f"/apis/{api}/invoke/{method}?confirm=true", body, timeout)

    def _list(self, path: str) -> list[dict[str, Any]]:
        return [dict(item) for item in self._read("GET", f"{self._ns}{path}")]

    def transaction_operations(self, transaction_id: str) -> list[Operation]:
        """The operations of a transaction, for example to see whether an earlier attempt failed."""
        body = self._read("GET", f"{self._ns}/transactions/{transaction_id}/operations")
        return [parse_operation(item) for item in body]

    def transaction_events(self, transaction_id: str) -> list[TxEvent]:
        """FireFly's own events for a transaction (submitted, operation succeeded or failed).
        Blockchain events are not here: they exist only for a registered contract listener."""
        return parse_events(self._read("GET", f"{self._ns}/events?tx={transaction_id}"))

    def get_operation(self, operation_id: str) -> Operation:
        return parse_operation(self._read("GET", f"{self._ns}/operations/{operation_id}"))

    def _write(self, path: str, body: dict[str, Any], timeout: float) -> Operation:
        try:
            status, answer = self._call("POST", f"{self._ns}{path}", body)
        except FireflyError as error:
            if _may_have_been_sent(error.__cause__):
                raise WriteUnconfirmed(
                    f"{error}; the write may or may not have been accepted"
                ) from error
            raise
        original = already_submitted_transaction(status, answer)
        if original is not None:
            raise AlreadySubmitted(original)
        self._raise_for(status, answer)
        return self._settle(parse_operation(answer), timeout)

    def _settle(self, operation: Operation, timeout: float) -> Operation:
        """Return a succeeded operation, raise for a failed one, poll while it is pending."""
        deadline = self._clock() + timeout
        while True:
            if operation.succeeded:
                return operation
            if operation.failed:
                raise OperationFailed(operation.id, operation.error)
            if self._clock() >= deadline:
                raise OperationTimeout(operation.id, operation.status, timeout)
            self._sleep(1.0)
            try:
                operation = self.get_operation(operation.id)
            except FireflyError as error:
                raise WriteUnconfirmed(
                    f"lost contact with FireFly while waiting for operation {operation.id}: "
                    f"{error}",
                    operation.id,
                ) from error

    def _read(self, method: str, path: str, body: Any = None) -> Any:
        """A request that changes nothing (a GET, a query, an ABI conversion). A timeout or a
        dropped connection says nothing about the request, so it is repeated a few times."""
        retries = 0
        while True:
            try:
                status, answer = self._call(method, path, body)
                self._raise_for(status, answer)
                return answer
            except FireflyError as error:
                retries += 1
                if retries > READ_RETRIES or not is_transient(str(error)):
                    raise
                self._sleep(2.0 * retries)

    def _call(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        try:
            return self._send(method, path, body)
        except OSError as error:
            raise FireflyError(f"{method} {path} could not reach FireFly: {error}") from error

    @staticmethod
    def _raise_for(status: int, body: Any) -> None:
        if 200 <= status < 300:
            return
        message = body.get("error") if isinstance(body, Mapping) else body
        text = f"HTTP {status}: {message}"
        reason = revert_reason(str(message))
        if reason is not None:
            raise Reverted(reason, text)
        raise FireflyError(text)
