"""The T-REX (ERC-3643) deployment plan (pure data and validation, no I/O).

The order and the arguments come from the contracts' own constructors and from `TREXFactory`
(`@tokenysolutions/t-rex` 4.1.6 with `@onchain-id/solidity` 2.1.0), see `docs/spike-results.md`,
"Phase 2 findings". A plan is a list of steps run in order through FireFly: deploy a contract, or
call a method on one that is already deployed.

Arguments are plain values, `Ref(name)` (the address of a contract deployed earlier in the plan),
`Account(name)` (the address of a demo wallet), or lists and dicts holding those (a Solidity
struct is a dict).
"""

from dataclasses import dataclass
from typing import Any

# Version registered in the TREXImplementationAuthority; it is the version of the t-rex package.
TREX_VERSION = {"major": 4, "minor": 1, "patch": 6}
KNOWN_ACCOUNTS = frozenset({"admin", "anson", "beatrice"})

ZERO_ADDRESS = "0x" + "00" * 20
COIN_SALT = "coin"  # the factory finds the token again by this salt (`getToken`)
COIN_NAME = "Coin"
COIN_SYMBOL = "COIN"
COIN_DECIMALS = 18
KYC_TOPIC = 1  # the claim topic an identity needs to be verified


class PlanError(Exception):
    """The plan refers to something that does not exist yet, or repeats a name."""


@dataclass(frozen=True)
class Ref:
    """The address of a contract deployed earlier in the plan."""

    name: str


@dataclass(frozen=True)
class Account:
    """The address of a demo wallet (`admin`, `anson` or `beatrice`)."""

    name: str


@dataclass(frozen=True)
class Artifact:
    """Where a contract's ABI and bytecode live: an npm package and a path below its
    `artifacts/contracts/` folder."""

    package: str  # "t-rex" or "onchainid"
    path: str


@dataclass(frozen=True)
class Deploy:
    name: str
    artifact: Artifact
    args: tuple[Any, ...] = ()


@dataclass(frozen=True)
class Call:
    contract: str
    method: str
    args: tuple[Any, ...]
    sender: str = "admin"


Step = Deploy | Call


def _onchainid(path: str) -> Artifact:
    return Artifact("onchainid", path)


def _trex(path: str) -> Artifact:
    return Artifact("t-rex", path)


_IMPLEMENTATIONS = {
    "token-implementation": ("token/Token.sol/Token.json", "tokenImplementation"),
    "claim-topics-registry-implementation": (
        "registry/implementation/ClaimTopicsRegistry.sol/ClaimTopicsRegistry.json",
        "ctrImplementation",
    ),
    "identity-registry-implementation": (
        "registry/implementation/IdentityRegistry.sol/IdentityRegistry.json",
        "irImplementation",
    ),
    "identity-registry-storage-implementation": (
        "registry/implementation/IdentityRegistryStorage.sol/IdentityRegistryStorage.json",
        "irsImplementation",
    ),
    "trusted-issuers-registry-implementation": (
        "registry/implementation/TrustedIssuersRegistry.sol/TrustedIssuersRegistry.json",
        "tirImplementation",
    ),
    "modular-compliance-implementation": (
        "compliance/modular/ModularCompliance.sol/ModularCompliance.json",
        "mcImplementation",
    ),
}


def build_plan() -> list[Step]:
    """The T-REX infrastructure, then the creation of the `COIN` token through the factory."""
    plan: list[Step] = [
        # OnchainID: the identity implementation (a library), its authority, and the factory
        # that creates one identity proxy per wallet.
        Deploy(
            "identity-implementation",
            _onchainid("Identity.sol/Identity.json"),
            (Account("admin"), True),
        ),
        Deploy(
            "identity-implementation-authority",
            _onchainid("proxy/ImplementationAuthority.sol/ImplementationAuthority.json"),
            (Ref("identity-implementation"),),
        ),
        Deploy(
            "id-factory",
            _onchainid("factory/IdFactory.sol/IdFactory.json"),
            (Ref("identity-implementation-authority"),),
        ),
    ]
    # T-REX: the six implementation contracts the proxies delegate to (no constructor arguments).
    for name, (path, _field) in _IMPLEMENTATIONS.items():
        plan.append(Deploy(name, _trex(path)))
    plan += [
        # The authority starts without a factory (the factory needs the authority's address).
        Deploy(
            "trex-implementation-authority",
            _trex("proxy/authority/TREXImplementationAuthority.sol/TREXImplementationAuthority.json"),
            (True, ZERO_ADDRESS, ZERO_ADDRESS),
        ),
        # The factory's constructor reverts unless the authority already holds all six
        # implementations, so the version is added before the factory is deployed.
        Call(
            "trex-implementation-authority",
            "addAndUseTREXVersion",
            (
                dict(TREX_VERSION),
                {field: Ref(name) for name, (_path, field) in _IMPLEMENTATIONS.items()},
            ),
        ),
        Deploy(
            "trex-factory",
            _trex("factory/TREXFactory.sol/TREXFactory.json"),
            (Ref("trex-implementation-authority"), Ref("id-factory")),
        ),
        # Admin is the claim issuer's management key, so Admin can sign KYC claims.
        Deploy(
            "claim-issuer",
            _onchainid("ClaimIssuer.sol/ClaimIssuer.json"),
            (Account("admin"),),
        ),
        # Register the factory with the authority and with the identity factory.
        Call("trex-implementation-authority", "setTREXFactory", (Ref("trex-factory"),)),
        Call("id-factory", "addTokenFactory", (Ref("trex-factory"),)),
        # Create COIN: the token, its identity registry (with a new storage), claim topics
        # registry, trusted issuers registry and modular compliance, all as proxies. Admin owns
        # them and is an agent of the registry and the token, so it can register, mint and pause.
        Call(
            "trex-factory",
            "deployTREXSuite",
            (
                COIN_SALT,
                {
                    "owner": Account("admin"),
                    "name": COIN_NAME,
                    "symbol": COIN_SYMBOL,
                    "decimals": COIN_DECIMALS,
                    "irs": ZERO_ADDRESS,
                    "ONCHAINID": ZERO_ADDRESS,
                    "irAgents": [Account("admin")],
                    "tokenAgents": [Account("admin")],
                    "complianceModules": [],
                    "complianceSettings": [],
                },
                {
                    "claimTopics": [KYC_TOPIC],
                    "issuers": [Ref("claim-issuer")],
                    "issuerClaims": [[KYC_TOPIC]],
                },
            ),
        ),
    ]
    return plan


def validate_plan(plan: list[Step]) -> None:
    """Raise `PlanError` unless every reference points to something deployed earlier."""
    deployed: set[str] = set()
    for step in plan:
        if isinstance(step, Deploy):
            if step.name in deployed:
                raise PlanError(f"'{step.name}' is deployed twice")
            _check_args(step.name, step.args, deployed)
            deployed.add(step.name)
        else:
            if step.contract not in deployed:
                raise PlanError(
                    f"{step.method} calls '{step.contract}', which is not deployed before it"
                )
            _check_args(f"{step.contract}.{step.method}", step.args, deployed)
            if step.sender not in KNOWN_ACCOUNTS:
                raise PlanError(f"unknown account '{step.sender}' sends {step.method}")


def _check_args(owner: str, value: Any, deployed: set[str]) -> None:
    if isinstance(value, Ref):
        if value.name not in deployed:
            raise PlanError(f"'{owner}' uses '{value.name}', which is not deployed before it")
    elif isinstance(value, Account):
        if value.name not in KNOWN_ACCOUNTS:
            raise PlanError(f"'{owner}' uses unknown account '{value.name}'")
    elif isinstance(value, dict):
        for item in value.values():
            _check_args(owner, item, deployed)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_args(owner, item, deployed)
