import pytest

from src.core.treasury.money import MAX_AMOUNT_MINOR
from src.core.treasury.plan import (
    APIS,
    ROLE_ACCOUNTS,
    TREASURY_ACCOUNTS,
    build_plan,
)
from src.core.trex.plan import Account, Call, Deploy, PlanError, Ref, validate_plan


def test_plan_is_valid_for_the_treasury_accounts() -> None:
    validate_plan(build_plan(), TREASURY_ACCOUNTS)


def test_plan_is_refused_with_only_the_original_demo_accounts() -> None:
    with pytest.raises(PlanError, match="unknown account"):
        validate_plan(build_plan())


def test_two_tokens_then_the_request_contract_then_the_controllers() -> None:
    plan = build_plan()
    deploys = [s.name for s in plan if isinstance(s, Deploy)]
    assert deploys == ["cadc", "gbpc", "funding-request"]
    calls = [(s.contract, s.method, s.sender) for s in plan if isinstance(s, Call)]
    assert calls == [
        ("cadc", "setController", "admin"),
        ("gbpc", "setController", "admin"),
    ]
    assert all(s.args == (Ref("funding-request"),) for s in plan if isinstance(s, Call))


def test_both_tokens_use_the_same_artifact_with_their_own_name_and_symbol() -> None:
    cadc, gbpc = (s for s in build_plan() if isinstance(s, Deploy) and s.name in ("cadc", "gbpc"))
    assert cadc.artifact == gbpc.artifact
    assert cadc.args[1] == "CADC" and gbpc.args[1] == "GBPC"
    assert cadc.args[2] == gbpc.args[2] == Account("admin")


def test_funding_request_constructor_arguments() -> None:
    request = next(s for s in build_plan() if isinstance(s, Deploy) and s.name == "funding-request")
    cadc, gbpc, treasury, requesters, approvers, cap, min_rate, max_rate = request.args
    assert (cadc, gbpc, treasury) == (Ref("cadc"), Ref("gbpc"), Account("treasury"))
    assert requesters == (Account("ldn"),)
    assert approvers == (Account("tor"),)
    assert cap == MAX_AMOUNT_MINOR
    assert 0 < min_rate < 580000 < max_rate


def test_roles_map_wallets_to_the_contract_roles() -> None:
    assert ROLE_ACCOUNTS == {"requester": "ldn", "approver": "tor", "treasury": "treasury"}
    assert set(ROLE_ACCOUNTS.values()) <= TREASURY_ACCOUNTS


def test_each_contract_gets_an_api() -> None:
    assert [(api, name) for api, name, _ in APIS] == [
        ("cadc", "cadc"),
        ("gbpc", "gbpc"),
        ("funding-request", "funding-request"),
    ]
    deployed = {s.name for s in build_plan() if isinstance(s, Deploy)}
    assert {name for _, name, _ in APIS} <= deployed
