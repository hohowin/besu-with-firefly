"""A small JSON-RPC client for integration tests, standard library only."""

import json
import urllib.request
from typing import Any

RPC_ANSON = "http://localhost:8545"
RPC_BEATRICE = "http://localhost:8555"


def rpc_call(url: str, method: str, params: list[Any] | None = None, timeout: float = 10.0) -> Any:
    """Call one JSON-RPC method and return its `result`. Raises if the node returns an error."""
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    ).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (localhost)
        reply = json.loads(response.read())
    if "error" in reply:
        raise RuntimeError(f"{method} on {url} returned an error: {reply['error']}")
    return reply["result"]


def block_number(url: str) -> int:
    return int(rpc_call(url, "eth_blockNumber"), 16)


def peer_count(url: str) -> int:
    return int(rpc_call(url, "net_peerCount"), 16)
