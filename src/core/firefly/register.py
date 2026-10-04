"""Register a contract with FireFly as an interface and an API (pure orchestration)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from src.core.firefly.inputs import InputError

DEFAULT_VERSION = "1.0.0"


class RegistryPort(Protocol):
    def api_registered(self, name: str) -> bool: ...

    def ensure_interface(self, name: str, version: str, abi: Sequence[Any]) -> str: ...

    def ensure_api(self, name: str, interface_id: str, address: str) -> str: ...


@dataclass(frozen=True)
class Registration:
    interface_id: str
    api_id: str
    created: bool  # False when the API was already there for this interface and address


def abi_from_document(document: Any) -> list[dict[str, Any]]:
    """The ABI in a parsed JSON file: a raw array, or an artifact with an `abi` key."""
    abi = document.get("abi") if isinstance(document, dict) else document
    if not isinstance(abi, list) or not abi or not all(isinstance(item, dict) for item in abi):
        raise InputError("the file holds no ABI (expected a JSON array, or an object with 'abi')")
    return abi


def register_contract(
    port: RegistryPort, name: str, version: str, abi: Sequence[Any], address: str
) -> Registration:
    """Register the interface and then the API `name` at `address`. Safe to repeat; an API of
    that name that points elsewhere is the client's error, not silently reused."""
    existed = port.api_registered(name)
    interface_id = port.ensure_interface(name, version, abi)
    api_id = port.ensure_api(name, interface_id, address)
    return Registration(interface_id, api_id, created=not existed)
