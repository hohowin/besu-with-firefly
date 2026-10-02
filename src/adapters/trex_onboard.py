"""Onboard demo accounts: OnchainID identity and IdentityRegistry entry, through FireFly."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from src.adapters.trex_apis import API_REGISTRY
from src.adapters.trex_artifacts import LoadedArtifact
from src.core.firefly.operations import Operation, find_method
from src.core.trex.onboarding import (
    COUNTRY,
    ONBOARD_ACCOUNTS,
    AccountState,
    CreateIdentity,
    identity_from_answer,
    registration_steps,
)
from src.core.trex.plan import Artifact, Deploy, build_plan


class Firefly(Protocol):
    def generate_interface(self, abi: Sequence[Any]) -> dict[str, Any]: ...

    def query(self, address: str, method: Mapping[str, Any], inputs: Mapping[str, Any]) -> Any: ...

    def invoke(
        self,
        address: str,
        method: Mapping[str, Any],
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = ...,
    ) -> Operation: ...

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


def register_identities(
    client: Firefly,
    load: Callable[[Artifact], LoadedArtifact],
    addresses: Mapping[str, str],
    accounts: Mapping[str, str],
    log: Callable[[str], None],
) -> None:
    """Give each onboarded account an OnchainID and register it in the IdentityRegistry.

    Reads the state first and sends only the writes that are missing, so a second run sends
    nothing. Admin signs everything (it owns the IdFactory and is an agent of the registry).
    """
    admin = accounts["admin"]
    factory = addresses["id-factory"]
    step = next(s for s in build_plan() if isinstance(s, Deploy) and s.name == "id-factory")
    abi = load(step.artifact).abi
    methods = client.generate_interface(abi)

    def identity_of(wallet: str) -> str | None:
        answer = client.query(factory, find_method(methods, "getIdentity"), {"_wallet": wallet})
        return identity_from_answer(str(next(iter(answer.values()))))

    for name in ONBOARD_ACCOUNTS:
        wallet = accounts[name]
        registered = bool(client.api_query(API_REGISTRY, "contains", {"_userAddress": wallet}))
        for todo in registration_steps(name, AccountState(identity_of(wallet), registered)):
            if isinstance(todo, CreateIdentity):
                client.invoke(
                    factory,
                    find_method(methods, "createIdentity"),
                    {"_wallet": wallet, "_salt": name},
                    key=admin,
                )
                log(f"{name}  identity created")
            else:
                identity = identity_of(wallet)
                client.api_invoke(
                    API_REGISTRY,
                    "registerIdentity",
                    {"_userAddress": wallet, "_identity": identity, "_country": COUNTRY},
                    key=admin,
                )
                log(f"{name}  registered")
