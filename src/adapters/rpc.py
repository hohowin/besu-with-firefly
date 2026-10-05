"""Read the chain height of Besu RPC nodes over JSON-RPC (adapter, standard library only)."""

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping

from src.adapters.docker_stack import ChainHeights
from src.adapters.settings import service_url


def rpc_nodes(env: Mapping[str, str] = os.environ) -> dict[str, str]:
    """The RPC node's address: `BESU_RPC_URL`, or `http://localhost:8545` when it is not set."""
    return {"besu-rpc-anson": service_url("BESU_RPC_URL", "http://localhost:8545", env)}


RPC_NODES = rpc_nodes()


def _block_number(url: str, timeout: float) -> int:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []})
    request = urllib.request.Request(
        url, data=body.encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (localhost)
        return int(json.loads(response.read())["result"], 16)


def get_code(address: str, url: str = RPC_NODES["besu-rpc-anson"], timeout: float = 10.0) -> str:
    """The contract code at an address (`0x` when there is none)."""
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "eth_getCode", "params": [address, "latest"]}
    )
    request = urllib.request.Request(
        url, data=body.encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (localhost)
        return str(json.loads(response.read())["result"])


def chain_heights_reader(
    nodes: Mapping[str, str] = RPC_NODES, timeout: float = 5.0
) -> ChainHeights:
    """A reader that returns each node's height, or None for a node that cannot be reached."""

    def read() -> dict[str, int | None]:
        heights: dict[str, int | None] = {}
        for name, url in nodes.items():
            try:
                heights[name] = _block_number(url, timeout)
            except (OSError, ValueError, KeyError, urllib.error.URLError):
                heights[name] = None
        return heights

    return read
