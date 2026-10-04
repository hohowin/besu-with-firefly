"""What core needs from FireFly (the port), implemented by `src/adapters/firefly.py`."""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from src.core.firefly.operations import Operation, TxEvent


class FireflyPort(Protocol):
    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any: ...

    def api_invoke(
        self,
        api: str,
        method: str,
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = ...,
    ) -> Operation: ...

    def get_operation(self, operation_id: str) -> Operation: ...

    def transaction_events(self, transaction_id: str) -> list[TxEvent]: ...

    def ensure_interface(self, name: str, version: str, abi: Sequence[Any]) -> str: ...

    def ensure_api(self, name: str, interface_id: str, address: str) -> str: ...
