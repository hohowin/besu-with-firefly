"""FireFly HTTP client (adapter, standard library only).

The transport is injected, so the client is tested without Docker. Writes use `?confirm=true`,
so FireFly answers with the final operation; a still-pending operation is polled with a bound.
"""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.core.firefly.operations import (
    Operation,
    already_submitted_transaction,
    deploy_body,
    invoke_body,
    parse_operation,
    query_body,
)

# (HTTP method, path, JSON body or None) -> (HTTP status, parsed JSON or text).
Transport = Callable[[str, str, Any], tuple[int, Any]]


class FireflyError(Exception):
    """A FireFly call failed. The message carries FireFly's own error text."""


class OperationFailed(FireflyError):
    def __init__(self, operation_id: str, error: str | None) -> None:
        super().__init__(f"operation {operation_id} failed: {error or 'no error text'}")
        self.operation_id = operation_id
        self.error = error


class OperationTimeout(FireflyError):
    def __init__(self, operation_id: str, status: str, timeout: float) -> None:
        super().__init__(f"operation {operation_id} is still {status} after {timeout:g}s")
        self.operation_id = operation_id


class AlreadySubmitted(FireflyError):
    """The idempotency key was used before: the write was accepted earlier, not repeated."""

    def __init__(self, transaction_id: str) -> None:
        super().__init__(f"already submitted as transaction {transaction_id}")
        self.transaction_id = transaction_id


@dataclass(frozen=True)
class DeployResult:
    address: str
    operation: Operation


def http_transport(base_url: str = "http://localhost:5000", timeout: float = 150.0) -> Transport:
    """A transport over `urllib`. The long timeout covers `confirm=true`, which blocks."""

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
        status, body = self._call("GET", "/api/v1/status")
        self._raise_for(status, body)
        return dict(body)

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
        status, body = self._call(
            "POST", f"{self._ns}/contracts/query", query_body(address, method, inputs)
        )
        self._raise_for(status, body)
        return body

    def generate_interface(self, abi: Sequence[Any]) -> dict[str, Any]:
        """Ask FireFly to turn an ABI into a contract interface (FFI). Nothing is registered."""
        status, body = self._call(
            "POST", f"{self._ns}/contracts/interfaces/generate", {"input": {"abi": list(abi)}}
        )
        self._raise_for(status, body)
        return dict(body)

    def transaction_operations(self, transaction_id: str) -> list[Operation]:
        """The operations of a transaction, for example to see whether an earlier attempt failed."""
        status, body = self._call("GET", f"{self._ns}/transactions/{transaction_id}/operations")
        self._raise_for(status, body)
        return [parse_operation(item) for item in body]

    def get_operation(self, operation_id: str) -> Operation:
        status, body = self._call("GET", f"{self._ns}/operations/{operation_id}")
        self._raise_for(status, body)
        return parse_operation(body)

    def _write(self, path: str, body: dict[str, Any], timeout: float) -> Operation:
        status, answer = self._call("POST", f"{self._ns}{path}", body)
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
            operation = self.get_operation(operation.id)

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
        raise FireflyError(f"HTTP {status}: {message}")
