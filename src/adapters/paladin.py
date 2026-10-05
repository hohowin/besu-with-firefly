"""Paladin JSON-RPC client (adapter, standard library only).

The transport is injected, so the client is tested without Docker. Reads are repeated a few times
when they time out; a transaction is sent once, because sending is not idempotent.
"""

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from src.adapters.settings import service_url
from src.core.paladin.rpc import (
    PaladinRpcError,
    ReceiptState,
    classify_receipt,
    is_transient,
    request_body,
    unwrap,
)

# (URL, JSON-RPC request body) -> parsed JSON-RPC reply.
Transport = Callable[[str, dict[str, Any]], dict[str, Any]]

_NODE_DEFAULTS = {  # the published HTTP RPC port of each node (see docker-compose.yml)
    "node1": "http://localhost:8548",
    "node2": "http://localhost:8648",
    "node3": "http://localhost:8748",
}


def paladin_nodes(env: Mapping[str, str] = os.environ) -> dict[str, str]:
    """Each node's RPC address from `PALADIN_NODE1_URL` to `PALADIN_NODE3_URL`, else its port."""
    return {
        node: service_url(f"PALADIN_{node.upper()}_URL", default, env)
        for node, default in _NODE_DEFAULTS.items()
    }


PALADIN_NODES = paladin_nodes()
READ_RETRIES = 3


class TransactionFailed(PaladinRpcError):
    """A transaction was mined or finalised as a failure. The message has Paladin's text."""

    def __init__(self, transaction_id: str, message: str) -> None:
        super().__init__(f"transaction {transaction_id} failed: {message}")
        self.transaction_id = transaction_id


class ReceiptTimeout(PaladinRpcError):
    def __init__(self, transaction_id: str, timeout: float) -> None:
        super().__init__(f"no receipt for transaction {transaction_id} after {timeout:g}s")
        self.transaction_id = transaction_id


def http_transport(timeout: float = 120.0) -> Transport:
    def send(url: str, body: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                reply: dict[str, Any] = json.loads(response.read())
                return reply
        except urllib.error.HTTPError as error:
            raise PaladinRpcError(f"HTTP {error.code}: {error.read()[:300]!r}") from error

    return send


class PaladinClient:
    def __init__(
        self,
        nodes: Mapping[str, str],
        transport: Transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._nodes = dict(nodes)
        self._send = transport
        self._sleep = sleep
        self._clock = clock

    def call(self, node: str, method: str, params: list[Any] | None = None) -> Any:
        """A read. A timeout or a dropped connection is repeated a few times."""
        return self._request(node, method, params or [], retry=True)

    def send_transaction(self, node: str, transaction: Mapping[str, Any]) -> str:
        """Submit a transaction and return its id. Never repeated: sending is not idempotent."""
        return str(self._request(node, "ptx_sendTransaction", [dict(transaction)], retry=False))

    def send_and_wait(
        self,
        node: str,
        transaction: Mapping[str, Any],
        timeout: float = 120.0,
        interval: float = 1.0,
    ) -> dict[str, Any]:
        """Submit a transaction and wait for its receipt. Raises if it failed or never finished."""
        transaction_id = self.send_transaction(node, transaction)
        deadline = self._clock() + timeout
        while True:
            receipt = self.call(node, "ptx_getTransactionReceipt", [transaction_id])
            state = classify_receipt(receipt)
            if state is ReceiptState.SUCCESS:
                return dict(receipt)
            if state is ReceiptState.FAILED:
                text = receipt.get("failureMessage") or json.dumps(receipt)[:500]
                raise TransactionFailed(transaction_id, str(text))
            if self._clock() >= deadline:
                raise ReceiptTimeout(transaction_id, timeout)
            self._sleep(interval)

    def private_call(self, node: str, call: Mapping[str, Any]) -> Any:
        """A read-only call to a private contract (`ptx_call`), for example `balanceOf`."""
        return self.call(node, "ptx_call", [dict(call)])

    def _request(self, node: str, method: str, params: list[Any], retry: bool) -> Any:
        if node not in self._nodes:
            raise ValueError(
                f"unknown Paladin node {node!r}, expected one of {sorted(self._nodes)}"
            )
        retries = 0
        while True:
            try:
                return unwrap(self._send(self._nodes[node], request_body(method, params)))
            except (OSError, PaladinRpcError) as error:
                retries += 1
                if not retry or retries > READ_RETRIES or not is_transient(str(error)):
                    if isinstance(error, PaladinRpcError):
                        raise
                    raise PaladinRpcError(f"{method} on {node}: {error}") from error
                self._sleep(2.0 * retries)
