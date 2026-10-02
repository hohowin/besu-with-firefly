"""Register FireFly contract interfaces and APIs for COIN and unpause the token (adapter)."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from src.adapters.trex_artifacts import LoadedArtifact
from src.core.firefly.operations import Operation
from src.core.trex.plan import Artifact, Deploy, build_plan

API_COIN = "coin"
API_REGISTRY = "identity-registry"
INTERFACE_VERSION = "1.0.0"

# API name, the suite contract it points at, and the plan contract whose ABI describes it.
_APIS = [
    (API_COIN, "token", "token-implementation"),
    (API_REGISTRY, "identity-registry", "identity-registry-implementation"),
]


class Registrar(Protocol):
    def ensure_interface(self, name: str, version: str, abi: Sequence[Any]) -> str: ...

    def ensure_api(self, name: str, interface_id: str, address: str) -> str: ...


class TokenApi(Protocol):
    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any: ...

    def api_invoke(
        self,
        api: str,
        method: str,
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = ...,
    ) -> Operation: ...


def register_apis(
    client: Registrar,
    load: Callable[[Artifact], LoadedArtifact],
    suite: Mapping[str, str],
    log: Callable[[str], None],
) -> None:
    """Register an interface and a contract API for the token and for the identity registry.

    Safe to repeat: what is already registered for the same address is reused.
    """
    artifacts = {s.name: s.artifact for s in build_plan() if isinstance(s, Deploy)}
    for api, suite_name, plan_name in _APIS:
        interface_id = client.ensure_interface(
            api, INTERFACE_VERSION, load(artifacts[plan_name]).abi
        )
        client.ensure_api(api, interface_id, suite[suite_name])
        log(f"api {api}  {suite[suite_name]}")


def unpause_token(client: TokenApi, admin: str, log: Callable[[str], None]) -> None:
    """A new T-REX token is paused. Unpause it as Admin (a token agent), unless it already is."""
    if client.api_query(API_COIN, "paused", {}) is False:
        log("token  (already unpaused)")
        return
    client.api_invoke(API_COIN, "unpause", {}, key=admin)
    log("token  unpaused")
