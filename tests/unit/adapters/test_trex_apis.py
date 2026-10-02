from collections.abc import Mapping
from typing import Any

from src.adapters.trex_apis import API_COIN, API_REGISTRY, register_apis, unpause_token
from src.adapters.trex_artifacts import LoadedArtifact
from src.core.firefly.operations import Operation
from src.core.trex.plan import Artifact

SUITE = {"token": "0x" + "01" * 20, "identity-registry": "0x" + "02" * 20}
ADMIN = "0x" + "aa" * 20


def load(artifact: Artifact) -> LoadedArtifact:
    return LoadedArtifact(artifact.path, [{"abi": artifact.path}], "0x", 1, 1)


class FakeClient:
    def __init__(self, paused: bool = True) -> None:
        self.paused = paused
        self.interfaces: list[tuple[str, str, Any]] = []
        self.apis: list[tuple[str, str, str]] = []
        self.invoked: list[tuple[str, str, dict[str, Any], str | None]] = []

    def ensure_interface(self, name: str, version: str, abi: Any) -> str:
        self.interfaces.append((name, version, abi))
        return f"if-{name}"

    def ensure_api(self, name: str, interface_id: str, address: str) -> str:
        self.apis.append((name, interface_id, address))
        return f"api-{name}"

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        assert (api, method) == (API_COIN, "paused")
        return self.paused

    def api_invoke(self, api: str, method: str, inputs: Mapping[str, Any], key: str | None = None,
                   idempotency_key: str | None = None, timeout: float = 0) -> Operation:
        self.invoked.append((api, method, dict(inputs), key))
        self.paused = False
        return Operation("op", "Succeeded")


def test_an_interface_and_an_api_are_registered_for_the_token_and_the_registry() -> None:
    client = FakeClient()
    register_apis(client, load, SUITE, lambda _line: None)
    assert [(n, v) for n, v, _ in client.interfaces] == [
        (API_COIN, "1.0.0"),
        (API_REGISTRY, "1.0.0"),
    ]
    assert client.apis == [
        (API_COIN, f"if-{API_COIN}", SUITE["token"]),
        (API_REGISTRY, f"if-{API_REGISTRY}", SUITE["identity-registry"]),
    ]


def test_the_token_abi_goes_to_the_coin_interface_and_the_registry_abi_to_the_other() -> None:
    client = FakeClient()
    register_apis(client, load, SUITE, lambda _line: None)
    by_name = {n: abi for n, _v, abi in client.interfaces}
    assert "Token.json" in by_name[API_COIN][0]["abi"]
    assert "IdentityRegistry.json" in by_name[API_REGISTRY][0]["abi"]


def test_a_paused_token_is_unpaused_by_admin_through_the_api() -> None:
    client = FakeClient(paused=True)
    unpause_token(client, ADMIN, lambda _line: None)
    assert client.invoked == [(API_COIN, "unpause", {}, ADMIN)]
    assert client.paused is False


def test_a_token_that_is_not_paused_is_left_alone() -> None:
    client = FakeClient(paused=False)
    unpause_token(client, ADMIN, lambda _line: None)
    assert client.invoked == []
