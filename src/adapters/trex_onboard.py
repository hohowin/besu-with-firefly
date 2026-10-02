"""Onboard demo accounts: OnchainID identity and IdentityRegistry entry, through FireFly."""

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from src.adapters.trex_apis import API_COIN, API_REGISTRY
from src.adapters.trex_artifacts import LoadedArtifact
from src.adapters.trex_deploy import DeployStepError, submit
from src.core.firefly.operations import Operation, find_method
from src.core.trex.amounts import MINT_AMOUNT, mint_needed, to_base_units
from src.core.trex.claims import KYC_CLAIM_DATA, SCHEME_ECDSA, needs_claim, sign_claim
from src.core.trex.onboarding import (
    COUNTRY,
    ONBOARD_ACCOUNTS,
    AccountState,
    CreateIdentity,
    identity_from_answer,
    registration_steps,
)
from src.core.trex.plan import KYC_TOPIC, Artifact, Deploy, build_plan


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

    def transaction_operations(self, transaction_id: str) -> list[Operation]: ...

    def api_invoke(
        self,
        api: str,
        method: str,
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = ...,
    ) -> Operation: ...


class TokenApi(Protocol):
    """What minting needs from FireFly: reads and writes through the `coin` API."""

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

    def transaction_operations(self, transaction_id: str) -> list[Operation]: ...


def register_identities(
    client: Firefly,
    load: Callable[[Artifact], LoadedArtifact],
    addresses: Mapping[str, str],
    accounts: Mapping[str, str],
    log: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Give each onboarded account an OnchainID and register it in the IdentityRegistry.

    Reads the state first and sends only the writes that are missing, so a second run sends
    nothing. Admin signs everything (it owns the IdFactory and is an agent of the registry).
    """
    admin = accounts["admin"]
    factory = addresses["id-factory"]
    methods = client.generate_interface(_abi(load, "id-factory"))
    identity_of = _identity_lookup(client, factory, methods)

    for name in ONBOARD_ACCOUNTS:
        wallet = accounts[name]
        registered = bool(client.api_query(API_REGISTRY, "contains", {"_userAddress": wallet}))
        for todo in registration_steps(name, AccountState(identity_of(wallet), registered)):
            if isinstance(todo, CreateIdentity):

                def create(key: str, wallet: str = wallet, name: str = name) -> Operation:
                    return client.invoke(
                        factory,
                        find_method(methods, "createIdentity"),
                        {"_wallet": wallet, "_salt": name},
                        key=admin,
                        idempotency_key=key,
                    )

                submit(name, create, f"trex-createIdentity-{name}", client, sleep, clock)
                log(f"{name}  identity created")
            else:
                identity = identity_of(wallet)

                def register(
                    key: str, wallet: str = wallet, identity: str | None = identity
                ) -> Operation:
                    return client.api_invoke(
                        API_REGISTRY,
                        "registerIdentity",
                        {"_userAddress": wallet, "_identity": identity, "_country": COUNTRY},
                        key=admin,
                        idempotency_key=key,
                    )

                submit(name, register, f"trex-registerIdentity-{name}", client, sleep, clock)
                log(f"{name}  registered")


def _abi(load: Callable[[Artifact], LoadedArtifact], plan_name: str) -> list[dict[str, Any]]:
    step = next(s for s in build_plan() if isinstance(s, Deploy) and s.name == plan_name)
    return load(step.artifact).abi


def _identity_lookup(
    client: Firefly, factory: str, methods: Mapping[str, Any]
) -> Callable[[str], str | None]:
    def identity_of(wallet: str) -> str | None:
        answer = client.query(factory, find_method(methods, "getIdentity"), {"_wallet": wallet})
        return identity_from_answer(str(next(iter(answer.values()))))

    return identity_of


def issue_claims(
    client: Firefly,
    load: Callable[[Artifact], LoadedArtifact],
    addresses: Mapping[str, str],
    accounts: Mapping[str, str],
    issuer_key: str,
    log: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Make each registered investor `isVerified` by giving their identity a signed KYC claim.

    The `ClaimIssuer` is managed by Admin, so Admin's key (`issuer_key`) signs the claim. The
    claim is added by the identity's owner (the investor's own FireFly key), as OnchainID
    requires. An account that is already verified is skipped, so a second run sends nothing.
    """
    factory_methods = client.generate_interface(_abi(load, "id-factory"))
    identity_methods = client.generate_interface(_abi(load, "identity-implementation"))
    identity_of = _identity_lookup(client, addresses["id-factory"], factory_methods)

    for name in ONBOARD_ACCOUNTS:
        wallet = accounts[name]
        identity = identity_of(wallet)
        verified = bool(client.api_query(API_REGISTRY, "isVerified", {"_userAddress": wallet}))
        try:
            needed = needs_claim(name, identity, verified)
        except ValueError as error:
            raise DeployStepError(name, str(error)) from error
        if not needed or identity is None:
            continue
        claim = {
            "_topic": KYC_TOPIC,
            "_scheme": SCHEME_ECDSA,
            "_issuer": addresses["claim-issuer"],
            "_signature": sign_claim(issuer_key, identity, KYC_TOPIC, KYC_CLAIM_DATA),
            "_data": "0x" + KYC_CLAIM_DATA.hex(),
            "_uri": "",
        }

        def add_claim(
            key: str, identity: str = identity, wallet: str = wallet, claim: dict[str, Any] = claim
        ) -> Operation:
            return client.invoke(
                identity,
                find_method(identity_methods, "addClaim"),
                claim,
                key=wallet,
                idempotency_key=key,
            )

        submit(name, add_claim, f"trex-addClaim-{name}", client, sleep, clock)
        log(f"{name}  verified (KYC claim added)")


def mint_initial_supply(
    client: TokenApi,
    accounts: Mapping[str, str],
    log: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Mint the initial supply (1000 COIN) to Anson as Admin, unless it has been minted.

    The check is the total supply, not Anson's balance, because Anson's balance drops once he
    transfers. Anson must be verified first or the token refuses the mint.
    """
    if not mint_needed(client.api_query(API_COIN, "totalSupply", {})):
        return
    anson = accounts["anson"]
    inputs = {"_to": anson, "_amount": str(to_base_units(MINT_AMOUNT))}

    def mint(key: str) -> Operation:
        return client.api_invoke(
            API_COIN, "mint", inputs, key=accounts["admin"], idempotency_key=key
        )

    submit("coin.mint", mint, "trex-mint-anson", client, sleep, clock)
    log(f"coin  minted {MINT_AMOUNT} to anson")
