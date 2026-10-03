"""The Paladin bootstrap: deploy the contracts, write the final configs, restart the nodes."""

import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol

from src.core.paladin.artifacts import PaladinArtifact
from src.core.paladin.bootstrap import (
    ADDRESS_NAMES,
    CONTRACT_ORDER,
    DEPLOY_NODE,
    deploy_params,
    final_config,
)
from src.core.paladin.config import NODES
from src.core.paladin.rpc import PaladinRpcError

MAX_RUNTIME_BYTES = 24_576  # EIP-170: runtime code of a contract
DOMAIN = "noto"


class PaladinBootstrapError(Exception):
    """A step of the bootstrap failed. `step` names the contract or node."""

    def __init__(self, step: str, reason: str) -> None:
        super().__init__(f"{step}: {reason}")
        self.step = step


class PaladinNode(Protocol):
    def send_and_wait(
        self, node: str, transaction: Mapping[str, Any], timeout: float = ..., interval: float = ...
    ) -> dict[str, Any]: ...

    def call(self, node: str, method: str, params: list[Any] | None = None) -> Any: ...


def deploy_contracts(
    client: PaladinNode,
    load: Callable[[str], PaladinArtifact],
    existing: Mapping[str, str],
    code_at: Callable[[str], str],
    save: Callable[[dict[str, str]], None],
    log: Callable[[str], None],
) -> dict[str, str]:
    """Deploy the four contracts through node1, signed by Paladin's own derived keys.

    A contract that is in `existing` and still has code on chain is skipped. Each address is saved
    as soon as it is known. Returns the address of each contract by its short name.
    """
    addresses: dict[str, str] = {}
    for name in CONTRACT_ORDER:
        recorded = existing.get(ADDRESS_NAMES[name])
        if recorded and code_at(recorded) not in ("", "0x"):
            addresses[name] = recorded
            log(f"paladin {name}  {recorded}  (already deployed)")
            continue
        artifact = load(name)
        transaction = {
            "type": "public",
            "from": artifact.sender,
            "abi": artifact.abi,
            "bytecode": artifact.bytecode,
            "data": deploy_params(name, addresses),
        }
        try:
            receipt = client.send_and_wait(DEPLOY_NODE, transaction)
        except PaladinRpcError as error:
            raise PaladinBootstrapError(name, str(error)) from error
        address = str(receipt.get("contractAddress", ""))
        if not address:
            raise PaladinBootstrapError(name, "the receipt has no contract address")
        code = code_at(address)
        if code in ("", "0x"):
            raise PaladinBootstrapError(name, f"{address} has no code on chain")
        size = (len(code) - 2) // 2
        if size > MAX_RUNTIME_BYTES:
            raise PaladinBootstrapError(
                name, f"runtime code is {size} bytes, over the {MAX_RUNTIME_BYTES} limit"
            )
        addresses[name] = address
        save({ADDRESS_NAMES[name]: address})
        log(f"paladin {name}  {address}")
    return addresses


def write_runtime_configs(source: Path, runtime: Path, addresses: Mapping[str, str]) -> list[str]:
    """Write each node's final config (base plus domain and registry) into the runtime folder.

    Returns the nodes whose file changed; a file that already has the right content is left alone.
    """
    changed = []
    for node in NODES:
        base = (source / node / "pldconf.paladin.yaml").read_text(encoding="utf-8")
        final = final_config(
            base,
            registry=addresses["registry"],
            factory_proxy=addresses["noto_factory_proxy"],
        )
        target = runtime / node / "pldconf.paladin.yaml"
        if target.is_file() and target.read_text(encoding="utf-8") == final:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(final, encoding="utf-8", newline="\n")
        changed.append(node)
    return changed


def _domain_loaded(client: PaladinNode, node: str) -> bool:
    try:
        return DOMAIN in client.call(node, "domain_listDomains")
    except (PaladinRpcError, OSError):
        return False  # a node that is still starting does not answer yet


def deploy_paladin(
    client: PaladinNode,
    *,
    load: Callable[[str], PaladinArtifact],
    source: Path,
    runtime: Path,
    existing: Mapping[str, str],
    code_at: Callable[[str], str],
    save: Callable[[dict[str, str]], None],
    restart: Callable[[str], None],
    register: Callable[[str], None],
    log: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    ready_timeout: float = 180.0,
) -> dict[str, str]:
    """Bring Paladin from "nodes running" to "Noto loaded and the nodes registered".

    Safe to repeat: contracts that exist are kept, a config that is already final is not
    rewritten, and a node is restarted only if its config changed or its domain is not loaded.
    """
    addresses = deploy_contracts(client, load, existing, code_at, save, log)
    changed = set(write_runtime_configs(source, runtime, addresses))
    for node in NODES:
        if node in changed or not _domain_loaded(client, node):
            restart(f"paladin-{node}")
            log(f"paladin {node}  restarted with the {DOMAIN} domain")
            deadline = clock() + ready_timeout
            while not _domain_loaded(client, node):
                if clock() >= deadline:
                    raise PaladinBootstrapError(
                        node, f"the {DOMAIN} domain did not load within {ready_timeout:g}s"
                    )
                sleep(2.0)
    register(addresses["registry"])  # once every node has its domain and is answering
    return addresses
