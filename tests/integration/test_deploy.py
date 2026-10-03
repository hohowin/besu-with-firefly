"""`stack.py deploy`: the T-REX infrastructure is deployed through FireFly and wired together."""

import json
from typing import Any

import pytest

from src.adapters.docker_stack import REPO_ROOT
from src.adapters.trex_artifacts import load_artifact
from src.adapters.trex_suite import SUITE_NAMES
from src.core.paladin.bootstrap import ADDRESS_NAMES as PALADIN_NAMES
from src.core.trex.plan import Deploy, build_plan
from tests.support.deploy import abi_of, run_deploy
from tests.support.firefly import ff_get, ff_query
from tests.support.rpc import RPC_ANSON, rpc_call

ADDRESSES_FILE = REPO_ROOT / "deployed-addresses.json"
PLAN_NAMES = [step.name for step in build_plan() if isinstance(step, Deploy)]
ZERO = "0x" + "00" * 20

pytestmark = pytest.mark.integration


def deploy_operations() -> list[dict[str, Any]]:
    operations = ff_get("/api/v1/namespaces/default/operations?type=blockchain_deploy&limit=200")
    assert isinstance(operations, list)
    return operations


def invoke_operations() -> list[dict[str, Any]]:
    operations = ff_get("/api/v1/namespaces/default/operations?type=blockchain_invoke&limit=200")
    assert isinstance(operations, list)
    return operations


def test_every_contract_has_a_non_zero_address_with_code_on_chain(deployed: dict[str, str]) -> None:
    assert sorted(deployed) == sorted(PLAN_NAMES + SUITE_NAMES + list(PALADIN_NAMES.values()))
    for name, address in deployed.items():
        assert int(address, 16) != 0, f"{name} has the zero address"
        assert rpc_call(RPC_ANSON, "eth_getCode", [address, "latest"]) not in ("0x", ""), name


def test_every_contract_was_deployed_by_a_firefly_operation(deployed: dict[str, str]) -> None:
    succeeded = {
        str(op["output"]["contractLocation"]["address"]).lower()
        for op in deploy_operations()
        if op["status"] == "Succeeded"
    }
    for name in PLAN_NAMES:  # the token and its proxies are created by the factory, not deployed
        assert deployed[name].lower() in succeeded, f"FireFly has no deploy operation for {name}"


def test_the_deployed_code_is_the_pinned_artifact(deployed: dict[str, str]) -> None:
    for step in (s for s in build_plan() if isinstance(s, Deploy)):
        on_chain = rpc_call(RPC_ANSON, "eth_getCode", [deployed[step.name], "latest"])
        expected = (len(on_chain) - 2) // 2
        assert expected == load_artifact(step.artifact).deployed_size, step.name


def test_the_wiring_calls_took_effect(deployed: dict[str, str]) -> None:
    trex_factory = deployed["trex-factory"].lower()
    registered = ff_query(
        deployed["trex-implementation-authority"],
        abi_of("trex-implementation-authority"),
        "getTREXFactory",
        {},
    )
    assert str(next(iter(registered.values()))).lower() == trex_factory
    is_token_factory = ff_query(
        deployed["id-factory"],
        abi_of("id-factory"),
        "isTokenFactory",
        {"_factory": deployed["trex-factory"]},
    )
    assert next(iter(is_token_factory.values())) is True


def one(answer: dict[str, Any]) -> str:
    return str(next(iter(answer.values())))


def test_coin_reads_back_as_coin_and_its_suite_is_the_one_the_token_points_to(
    deployed: dict[str, str],
) -> None:
    token, registry = deployed["token"], deployed["identity-registry"]
    token_abi = abi_of("token-implementation")
    registry_abi = abi_of("identity-registry-implementation")
    assert one(ff_query(token, token_abi, "name", {})) == "Coin"
    assert one(ff_query(token, token_abi, "symbol", {})) == "COIN"
    assert one(ff_query(token, token_abi, "identityRegistry", {})).lower() == registry
    compliance = one(ff_query(token, token_abi, "compliance", {})).lower()
    assert compliance == deployed["modular-compliance"]
    assert (
        one(ff_query(registry, registry_abi, "identityStorage", {})).lower()
        == deployed["identity-registry-storage"]
    )
    assert (
        one(ff_query(registry, registry_abi, "topicsRegistry", {})).lower()
        == deployed["claim-topics-registry"]
    )
    assert (
        one(ff_query(registry, registry_abi, "issuersRegistry", {})).lower()
        == deployed["trusted-issuers-registry"]
    )


def test_the_suite_was_created_by_a_firefly_invoke_of_the_factory(deployed: dict[str, str]) -> None:
    created = [
        op
        for op in invoke_operations()
        if op["status"] == "Succeeded" and "deployTREXSuite" in str(op["input"])
    ]
    assert len(created) == 1


def test_running_deploy_again_sends_nothing_new(deployed: dict[str, str]) -> None:
    before = (len(deploy_operations()), len(invoke_operations()))
    result = run_deploy()
    assert result.returncode == 0, result.stderr
    assert "already deployed" in result.stdout
    assert (len(deploy_operations()), len(invoke_operations())) == before
    assert json.loads(ADDRESSES_FILE.read_text(encoding="utf-8")) == deployed
