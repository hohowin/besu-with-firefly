from collections.abc import Sequence
from typing import Any

import pytest

from src.core.firefly.errors import FireflyError
from src.core.firefly.inputs import InputError, check_address
from src.core.firefly.register import Registration, abi_from_document, register_contract

ABI = [{"type": "function", "name": "name", "inputs": [], "outputs": []}]
ADDRESS = "0x" + "ab" * 20


def test_a_raw_abi_array_and_an_artifact_with_an_abi_key_both_work() -> None:
    assert abi_from_document(ABI) == ABI
    assert abi_from_document({"contractName": "Token", "abi": ABI}) == ABI


@pytest.mark.parametrize("document", [{}, {"abi": []}, [], "text", [1, 2], {"abi": "x"}])
def test_anything_else_is_not_an_abi(document: Any) -> None:
    with pytest.raises(InputError, match="ABI"):
        abi_from_document(document)


def test_check_address_accepts_a_20_byte_hex_address_only() -> None:
    assert check_address(ADDRESS) == ADDRESS
    for bad in ["0x123", ADDRESS[:-1] + "g", ADDRESS.removeprefix("0x"), ""]:
        with pytest.raises(InputError, match="address"):
            check_address(bad)


class Port:
    def __init__(self, existing: bool = False, api_error: Exception | None = None) -> None:
        self.existing = existing
        self.api_error = api_error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def api_registered(self, name: str) -> bool:
        self.calls.append(("api_registered", (name,)))
        return self.existing

    def ensure_interface(self, name: str, version: str, abi: Sequence[Any]) -> str:
        self.calls.append(("ensure_interface", (name, version, list(abi))))
        return "ffi1"

    def ensure_api(self, name: str, interface_id: str, address: str) -> str:
        self.calls.append(("ensure_api", (name, interface_id, address)))
        if self.api_error:
            raise self.api_error
        return "api1"


def test_registering_a_new_contract_registers_the_interface_then_the_api() -> None:
    port = Port()
    result = register_contract(port, "coin-copy", "1.0.0", ABI, ADDRESS)
    assert result == Registration("ffi1", "api1", created=True)
    assert [name for name, _ in port.calls] == ["api_registered", "ensure_interface", "ensure_api"]
    assert port.calls[1][1] == ("coin-copy", "1.0.0", ABI)
    assert port.calls[2][1] == ("coin-copy", "ffi1", ADDRESS)


def test_registering_again_is_reported_as_already_registered() -> None:
    result = register_contract(Port(existing=True), "coin-copy", "1.0.0", ABI, ADDRESS)
    assert result == Registration("ffi1", "api1", created=False)


def test_the_same_name_for_another_address_is_the_clients_error() -> None:
    port = Port(existing=True, api_error=FireflyError("API 'x' already exists for another"))
    with pytest.raises(FireflyError, match="already exists"):
        register_contract(port, "x", "1.0.0", ABI, ADDRESS)
