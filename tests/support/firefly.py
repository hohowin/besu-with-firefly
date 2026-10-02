"""A tiny FireFly HTTP helper for integration tests, standard library only.

The real client is `src/adapters/firefly.py` (Task 4). Tests keep their own helper so that a bug in
the adapter cannot hide a bug in the stack.
"""

import json
import urllib.request
from typing import Any

FIREFLY = "http://localhost:5000"


def ff_get(path: str, timeout: float = 10.0) -> Any:
    with urllib.request.urlopen(f"{FIREFLY}{path}", timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read())


def ff_post(path: str, body: Any, timeout: float = 30.0) -> Any:
    request = urllib.request.Request(
        f"{FIREFLY}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read())


def ff_query(address: str, abi: list[Any], method: str, inputs: dict[str, Any]) -> Any:
    """Call a read-only method through FireFly, using FireFly's own ABI to method conversion."""
    generate = "/api/v1/namespaces/default/contracts/interfaces/generate"
    interface = ff_post(generate, {"input": {"abi": abi}})
    ffi = next(m for m in interface["methods"] if m["name"] == method)
    return ff_post(
        "/api/v1/namespaces/default/contracts/query",
        {"location": {"address": address}, "method": ffi, "input": inputs},
    )
