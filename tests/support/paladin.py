"""A tiny Paladin JSON-RPC helper for integration tests, standard library only.

The real client is `src/adapters/paladin.py`. Tests keep their own helper so that a bug in the
adapter cannot hide a bug in the stack.
"""

import json
import urllib.request
from typing import Any

# Published HTTP RPC port of each Paladin node.
PALADIN_PORTS = {"node1": 8548, "node2": 8648, "node3": 8748}


def paladin_call(
    node: str, method: str, params: list[Any] | None = None, timeout: float = 30.0
) -> Any:
    """Call one JSON-RPC method on a Paladin node and return its `result`."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []})
    request = urllib.request.Request(
        f"http://localhost:{PALADIN_PORTS[node]}",
        data=body.encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (localhost)
        reply = json.loads(response.read())
    if "error" in reply:
        raise RuntimeError(f"{method} on {node} returned an error: {reply['error']}")
    return reply["result"]
