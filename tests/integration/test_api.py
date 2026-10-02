"""The contract interfaces and APIs FireFly generates for COIN and the identity registry."""

import json
from typing import Any

import pytest

from src.adapters.docker_stack import REPO_ROOT
from tests.support.deploy import run_deploy
from tests.support.firefly import ff_get, ff_post

pytestmark = pytest.mark.integration

NS = "/api/v1/namespaces/default"


def one(answer: dict[str, Any]) -> Any:
    return answer["output"]


def admin_address() -> str:
    wallets = json.loads((REPO_ROOT / "network-config" / "wallets.json").read_text("utf-8"))
    return str(next(w["address"] for w in wallets["wallets"] if w["name"] == "admin"))


def test_apis_exist_for_the_token_and_the_identity_registry(deployed: dict[str, str]) -> None:
    apis = {api["name"]: api for api in ff_get(f"{NS}/apis")}
    assert {"coin", "identity-registry"} <= set(apis)
    assert apis["coin"]["location"]["address"].lower() == deployed["token"]
    assert apis["identity-registry"]["location"]["address"].lower() == deployed["identity-registry"]


def interface_methods(name: str) -> set[str]:
    listed = ff_get(f"{NS}/contracts/interfaces?name={name}")
    assert len(listed) == 1, f"expected one interface called {name}, found {len(listed)}"
    interface = ff_get(f"{NS}/contracts/interfaces/{listed[0]['id']}?fetchchildren=true")
    return {m["name"] for m in interface["methods"]}


def test_the_interfaces_carry_the_contract_abis(deployed: dict[str, str]) -> None:
    assert {"balanceOf", "mint", "transfer", "unpause", "paused"} <= interface_methods("coin")
    registry = interface_methods("identity-registry")
    assert {"registerIdentity", "isVerified", "contains"} <= registry


def test_a_read_through_the_generated_api_works(deployed: dict[str, str]) -> None:
    assert one(ff_post(f"{NS}/apis/coin/query/name", {})) == "Coin"
    assert one(ff_post(f"{NS}/apis/coin/query/symbol", {})) == "COIN"
    inputs = {"input": {"_userAddress": admin_address()}}
    assert one(ff_post(f"{NS}/apis/coin/query/balanceOf", inputs)) == "0"


def test_a_write_through_the_generated_api_took_effect(deployed: dict[str, str]) -> None:
    # `deploy` unpaused the token through the `coin` API as Admin.
    assert one(ff_post(f"{NS}/apis/coin/query/paused", {})) is False
    unpauses = [
        op
        for op in ff_get(f"{NS}/operations?type=blockchain_invoke&limit=200")
        if op["status"] == "Succeeded" and "unpause" in json.dumps(op["input"])
    ]
    assert unpauses, "no FireFly invoke operation for unpause"


def test_deploy_again_creates_no_duplicate_interfaces_or_apis(deployed: dict[str, str]) -> None:
    before = (len(ff_get(f"{NS}/apis")), len(ff_get(f"{NS}/contracts/interfaces")))
    result = run_deploy()
    assert result.returncode == 0, result.stderr
    assert (len(ff_get(f"{NS}/apis")), len(ff_get(f"{NS}/contracts/interfaces"))) == before
    assert "already unpaused" in result.stdout
