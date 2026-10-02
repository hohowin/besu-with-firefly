"""Registering the demo investors: OnchainID identity, then IdentityRegistry entry."""

import json
import subprocess
import sys
from typing import Any

import pytest

from src.adapters.docker_stack import REPO_ROOT
from tests.support.deploy import abi_of, run_deploy
from tests.support.firefly import ff_get, ff_post, ff_query
from tests.support.rpc import RPC_ANSON, rpc_call

pytestmark = pytest.mark.integration

NS = "/api/v1/namespaces/default"
ZERO = "0x" + "00" * 20


def wallets() -> dict[str, str]:
    document = json.loads((REPO_ROOT / "network-config" / "wallets.json").read_text("utf-8"))
    return {w["name"]: w["address"] for w in document["wallets"]}


def registry(method: str, **inputs: str) -> Any:
    return ff_post(f"{NS}/apis/identity-registry/query/{method}", {"input": inputs})["output"]


def operation_count() -> int:
    return len(ff_get(f"{NS}/operations?limit=500"))


def run_onboard() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "stack.py"), "onboard"],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def test_anson_and_beatrice_are_registered_and_admin_is_not(deployed: dict[str, str]) -> None:
    accounts = wallets()
    assert registry("contains", _userAddress=accounts["anson"]) is True
    assert registry("contains", _userAddress=accounts["beatrice"]) is True
    assert registry("contains", _userAddress=accounts["admin"]) is False


def test_each_investor_is_registered_with_a_real_onchainid(deployed: dict[str, str]) -> None:
    accounts = wallets()
    for name in ("anson", "beatrice"):
        wallet = accounts[name]
        created = ff_query(
            deployed["id-factory"], abi_of("id-factory"), "getIdentity", {"_wallet": wallet}
        )
        identity = str(next(iter(created.values()))).lower()
        assert identity != ZERO, f"{name} has no OnchainID"
        assert rpc_call(RPC_ANSON, "eth_getCode", [identity, "latest"]) not in ("0x", "")
        assert registry("identity", _userAddress=wallet).lower() == identity


def test_admin_has_no_onchainid(deployed: dict[str, str]) -> None:
    created = ff_query(
        deployed["id-factory"], abi_of("id-factory"), "getIdentity", {"_wallet": wallets()["admin"]}
    )
    assert str(next(iter(created.values()))).lower() == ZERO


def test_running_onboard_again_sends_no_transaction(deployed: dict[str, str]) -> None:
    before = operation_count()
    result = run_onboard()
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"onboard did something: {result.stdout}"
    assert operation_count() == before


def test_running_deploy_again_sends_no_onboarding_transaction(deployed: dict[str, str]) -> None:
    before = operation_count()
    assert run_deploy().returncode == 0
    assert operation_count() == before
