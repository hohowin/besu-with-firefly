import pytest

from src.core.trex.limits import MAX_DEPLOYED_BYTES, MAX_INIT_BYTES, size_problems
from src.core.trex.plan import (
    ZERO_ADDRESS,
    Account,
    Artifact,
    Call,
    Deploy,
    PlanError,
    Ref,
    build_plan,
    validate_plan,
)

ART = Artifact("t-rex", "x/X.sol/X.json")


def names(plan: list[Deploy | Call]) -> list[str]:
    return [step.name for step in plan if isinstance(step, Deploy)]


def index_of(plan: list[Deploy | Call], wanted: str) -> int:
    return next(i for i, s in enumerate(plan) if isinstance(s, Deploy) and s.name == wanted)


def test_the_default_plan_is_valid() -> None:
    validate_plan(build_plan())


def test_every_contract_name_is_unique() -> None:
    deployed = names(build_plan())
    assert len(deployed) == len(set(deployed))


def test_the_plan_deploys_the_twelve_contracts_the_suite_needs() -> None:
    assert set(names(build_plan())) == {
        "identity-implementation",
        "identity-implementation-authority",
        "id-factory",
        "token-implementation",
        "claim-topics-registry-implementation",
        "identity-registry-implementation",
        "identity-registry-storage-implementation",
        "trusted-issuers-registry-implementation",
        "modular-compliance-implementation",
        "trex-implementation-authority",
        "trex-factory",
        "claim-issuer",
    }


def test_the_onchainid_chain_is_deployed_in_dependency_order() -> None:
    plan = build_plan()
    assert (
        index_of(plan, "identity-implementation")
        < index_of(plan, "identity-implementation-authority")
        < index_of(plan, "id-factory")
        < index_of(plan, "trex-factory")
    )


def test_the_factory_needs_the_trex_authority_and_the_id_factory_first() -> None:
    plan = build_plan()
    factory = next(s for s in plan if isinstance(s, Deploy) and s.name == "trex-factory")
    assert factory.args == (Ref("trex-implementation-authority"), Ref("id-factory"))


def test_the_authority_is_complete_before_the_factory_is_deployed() -> None:
    """TREXFactory's constructor reverts ("invalid Implementation Authority") unless the authority
    already has all six implementations, so its version must be added first (seen on the chain)."""
    plan = build_plan()
    version_call = next(
        i for i, s in enumerate(plan) if isinstance(s, Call) and s.method == "addAndUseTREXVersion"
    )
    for implementation in (
        "token-implementation",
        "claim-topics-registry-implementation",
        "identity-registry-implementation",
        "identity-registry-storage-implementation",
        "trusted-issuers-registry-implementation",
        "modular-compliance-implementation",
        "trex-implementation-authority",
    ):
        assert index_of(plan, implementation) < version_call
    assert version_call < index_of(plan, "trex-factory")


def test_the_factory_is_registered_with_the_authority_and_the_id_factory_after_it_exists() -> None:
    plan = build_plan()
    by_method = {s.method: i for i, s in enumerate(plan) if isinstance(s, Call)}
    assert {"addAndUseTREXVersion", "setTREXFactory", "addTokenFactory"} <= set(by_method)
    assert index_of(plan, "trex-factory") < by_method["setTREXFactory"]
    assert index_of(plan, "trex-factory") < by_method["addTokenFactory"]


def test_the_claim_issuer_is_managed_by_the_admin_wallet() -> None:
    issuer = next(s for s in build_plan() if isinstance(s, Deploy) and s.name == "claim-issuer")
    assert issuer.args == (Account("admin"),)


def test_a_reference_to_a_contract_deployed_later_is_rejected() -> None:
    plan: list[Deploy | Call] = [Deploy("a", ART, (Ref("b"),)), Deploy("b", ART)]
    with pytest.raises(PlanError, match=r"'a'.*'b'.*not deployed before"):
        validate_plan(plan)


def test_a_duplicate_name_is_rejected() -> None:
    with pytest.raises(PlanError, match="deployed twice"):
        validate_plan([Deploy("a", ART), Deploy("a", ART)])


def test_a_call_on_an_unknown_contract_is_rejected() -> None:
    with pytest.raises(PlanError, match=r"calls .*'ghost'"):
        validate_plan([Call("ghost", "m", ())])


def test_a_reference_nested_inside_a_struct_or_list_is_checked_too() -> None:
    plan: list[Deploy | Call] = [Deploy("a", ART), Call("a", "m", ({"x": [Ref("missing")]},))]
    with pytest.raises(PlanError, match="'missing'"):
        validate_plan(plan)


def test_an_unknown_account_is_rejected() -> None:
    with pytest.raises(PlanError, match=r"unknown account 'bob'"):
        validate_plan([Deploy("a", ART, (Account("bob"),))])


def test_sizes_over_the_ethereum_limits_are_reported() -> None:
    assert size_problems("Token", MAX_DEPLOYED_BYTES, MAX_INIT_BYTES) == []
    deployed = size_problems("Token", MAX_DEPLOYED_BYTES + 1, 100)
    assert len(deployed) == 1 and "Token" in deployed[0] and "deployed" in deployed[0]
    init = size_problems("Token", 100, MAX_INIT_BYTES + 1)
    assert len(init) == 1 and "init" in init[0]
    assert MAX_DEPLOYED_BYTES == 24_576 and MAX_INIT_BYTES == 49_152


def test_the_token_is_created_last_by_the_factory_as_admin() -> None:
    plan = build_plan()
    create = plan[-1]
    assert isinstance(create, Call)
    assert (create.contract, create.method) == ("trex-factory", "deployTREXSuite")
    assert create.sender == "admin"
    registered = {s.method: i for i, s in enumerate(plan) if isinstance(s, Call)}
    assert registered["deployTREXSuite"] > registered["addTokenFactory"]
    assert registered["deployTREXSuite"] > registered["setTREXFactory"]
    assert index_of(plan, "claim-issuer") < registered["deployTREXSuite"]


def test_the_token_details_describe_coin() -> None:
    from src.core.trex.plan import COIN_DECIMALS, COIN_NAME, COIN_SALT, COIN_SYMBOL, KYC_TOPIC

    create = build_plan()[-1]
    assert isinstance(create, Call)
    salt, token, claims = create.args
    assert salt == COIN_SALT
    assert (token["name"], token["symbol"], token["decimals"]) == ("Coin", "COIN", 18)
    assert (COIN_NAME, COIN_SYMBOL, COIN_DECIMALS) == ("Coin", "COIN", 18)
    assert token["owner"] == Account("admin")
    assert token["irs"] == ZERO_ADDRESS  # a new identity registry storage is created
    assert token["ONCHAINID"] == ZERO_ADDRESS  # the factory creates the token's identity
    assert token["irAgents"] == [Account("admin")]
    assert token["tokenAgents"] == [Account("admin")]
    assert token["complianceModules"] == [] and token["complianceSettings"] == []
    assert claims == {
        "claimTopics": [KYC_TOPIC],
        "issuers": [Ref("claim-issuer")],
        "issuerClaims": [[KYC_TOPIC]],
    }
