"""Paladin JSON-RPC requests and replies (pure, no I/O)."""

from enum import Enum
from typing import Any


class PaladinRpcError(Exception):
    """A Paladin call failed. The message carries Paladin's own text; `code` is JSON-RPC's."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class ReceiptState(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


_TRANSIENT = (
    "context deadline exceeded",
    "timed out",
    "timeout",
    "connection refused",
    "connection reset",
    "http 502",
    "http 503",
    "http 504",
)


def request_body(method: str, params: list[Any], request_id: int = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


def unwrap(reply: dict[str, Any]) -> Any:
    """The `result` of a JSON-RPC reply, or a `PaladinRpcError` with the node's own message."""
    if "error" in reply:
        error = reply["error"]
        raise PaladinRpcError(str(error.get("message", error)), error.get("code"))
    if "result" not in reply:
        raise PaladinRpcError(f"not a JSON-RPC reply: {str(reply)[:200]}")
    return reply["result"]


def classify_receipt(receipt: dict[str, Any] | None) -> ReceiptState:
    """`ptx_getTransactionReceipt` answers null until the transaction is final."""
    if receipt is None:
        return ReceiptState.PENDING
    return ReceiptState.SUCCESS if receipt.get("success") else ReceiptState.FAILED


def is_transient(message: str) -> bool:
    """True for a failure that says nothing about the request (a timeout, a dropped connection),
    so repeating a read is reasonable. An error from Paladin or a contract is not transient."""
    text = message.lower()
    return any(marker in text for marker in _TRANSIENT)
