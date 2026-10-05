"""Service addresses from the environment (adapter).

The code reaches FireFly, Besu and Paladin at `localhost` ports when it runs on the host, and at
the Compose service names when it runs inside the `deployer` container. Each address is an
environment variable with today's `localhost` value as the default.
"""

import os
from collections.abc import Mapping
from urllib.parse import urlparse


def service_url(name: str, default: str, env: Mapping[str, str] = os.environ) -> str:
    """The address in environment variable `name`, or `default` when it is not set.

    A value that is blank or is not an `http://` or `https://` address with a host is refused,
    and the message names the variable, so a typo in Compose fails loudly and early.
    """
    if name not in env:
        return default
    value = env[name].strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"{name} must be an http:// or https:// address, got {env[name]!r}")
    return value.rstrip("/")
