"""Find the contracts the TREXFactory created for `COIN` and check the token (adapter)."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from src.adapters.firefly import FireflyError
from src.adapters.trex_artifacts import LoadedArtifact
from src.adapters.trex_deploy import DeployStepError
from src.core.firefly.operations import find_method
from src.core.trex.plan import (
    COIN_NAME,
    COIN_SALT,
    COIN_SYMBOL,
    ZERO_ADDRESS,
    Artifact,
    Deploy,
    build_plan,
)

SUITE_NAMES = [
    "token",
    "identity-registry",
    "identity-registry-storage",
    "claim-topics-registry",
    "trusted-issuers-registry",
    "modular-compliance",
]


class Querier(Protocol):
    def generate_interface(self, abi: Sequence[Any]) -> dict[str, Any]: ...

    def query(self, address: str, method: Mapping[str, Any], inputs: Mapping[str, Any]) -> Any: ...


def read_suite(
    client: Querier,
    load: Callable[[Artifact], LoadedArtifact],
    addresses: Mapping[str, str],
    code_at: Callable[[str], str],
) -> dict[str, str]:
    """The addresses of the token and its five proxies, each read from the contract that owns it.

    Starts at the factory (`getToken(salt)`), then reads the token and its identity registry.
    Checks the token's name and symbol, and that every address has code.
    """
    factory_abi = _abi(load, "trex-factory")
    token_abi = _abi(load, "token-implementation")
    registry_abi = _abi(load, "identity-registry-implementation")

    def ask(address: str, abi: list[dict[str, Any]], method: str, **inputs: Any) -> Any:
        try:
            ffi = find_method(client.generate_interface(abi), method)
            answer = client.query(address, ffi, inputs)
        except (FireflyError, ValueError) as error:
            raise DeployStepError("token", f"reading {method} failed: {error}") from error
        return next(iter(answer.values())) if isinstance(answer, Mapping) else answer

    token = str(ask(addresses["trex-factory"], factory_abi, "getToken", _salt=COIN_SALT)).lower()
    if int(token, 16) == 0 or token == ZERO_ADDRESS:
        raise DeployStepError("token", "not created: the factory has no token for this salt")
    for method, expected in (("name", COIN_NAME), ("symbol", COIN_SYMBOL)):
        found = ask(token, token_abi, method)
        if found != expected:
            raise DeployStepError("token", f"{method} should be {expected!r}, it is {found!r}")
    registry = str(ask(token, token_abi, "identityRegistry")).lower()
    suite = {
        "token": token,
        "identity-registry": registry,
        "identity-registry-storage": str(
            ask(registry, registry_abi, "identityStorage")
        ).lower(),
        "claim-topics-registry": str(ask(registry, registry_abi, "topicsRegistry")).lower(),
        "trusted-issuers-registry": str(ask(registry, registry_abi, "issuersRegistry")).lower(),
        "modular-compliance": str(ask(token, token_abi, "compliance")).lower(),
    }
    for name, address in suite.items():
        if code_at(address) in ("", "0x"):
            raise DeployStepError(name, f"{address} has no code on chain")
    return suite


def _abi(load: Callable[[Artifact], LoadedArtifact], plan_name: str) -> list[dict[str, Any]]:
    step = next(s for s in build_plan() if isinstance(s, Deploy) and s.name == plan_name)
    return load(step.artifact).abi
