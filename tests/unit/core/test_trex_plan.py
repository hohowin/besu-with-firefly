import pytest

from src.core.trex.limits import MAX_DEPLOYED_BYTES, MAX_INIT_BYTES, size_problems
from src.core.trex.plan import (
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


def test_the_authority_gets_its_version_and_factory_only_after_everything_exists() -> None:
    plan = build_plan()
    calls = [(i, s) for i, s in enumerate(plan) if isinstance(s, Call)]
    by_method = {s.method: i for i, s in calls}
    assert set(by_method) == {"addAndUseTREXVersion", "setTREXFactory", "addTokenFactory"}
    for implementation in (
        "token-implementation",
        "claim-topics-registry-implementation",
        "identity-registry-implementation",
        "identity-registry-storage-implementation",
        "trusted-issuers-registry-implementation",
        "modular-compliance-implementation",
    ):
        assert index_of(plan, implementation) < by_method["addAndUseTREXVersion"]
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
