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
