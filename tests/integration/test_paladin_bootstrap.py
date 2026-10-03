"""`stack.py deploy` bootstraps Paladin: contracts deployed by its own keys, Noto domain loaded."""

from typing import Any

import pytest

from src.adapters.addresses import read_addresses
from src.adapters.docker_stack import DockerStack
from src.core.paladin.bootstrap import ADDRESS_NAMES
from tests.support.deploy import run_deploy
from tests.support.firefly import ff_get
from tests.support.paladin import PALADIN_PORTS, paladin_call
from tests.support.rpc import RPC_ANSON, rpc_call

pytestmark = pytest.mark.integration

MAX_RUNTIME_BYTES = 24_576
# The Paladin key (label) that deploys each contract (read from the vendored artifacts).
SENDERS = {
    "registry": "registry.operator",
    "noto": "noto.operator",
    "noto_factory": "noto_factory.operator",
    "noto_factory_proxy": "noto_factory_proxy.operator",
}


def paladin_addresses() -> dict[str, str]:
    recorded = read_addresses()
    return {short: recorded[name] for short, name in ADDRESS_NAMES.items()}


def started_at(stack: DockerStack) -> dict[str, str]:
    return {node: stack.started_at(f"paladin-{node}") for node in PALADIN_PORTS}


def test_the_four_contracts_have_non_zero_addresses_with_code_that_fits(
    deployed: dict[str, str],
) -> None:
    for short, address in paladin_addresses().items():
        assert int(address, 16) != 0, short
        code = rpc_call(RPC_ANSON, "eth_getCode", [address, "latest"])
        assert code not in ("0x", ""), short
        assert (len(code) - 2) // 2 <= MAX_RUNTIME_BYTES, short


def test_paladins_own_keys_deployed_them_and_firefly_did_not(deployed: dict[str, str]) -> None:
    receipts = paladin_call("node1", "ptx_queryTransactionReceipts", [{"limit": 100}])
    by_contract = {r["contractAddress"].lower(): r for r in receipts if r.get("contractAddress")}
    for short, address in paladin_addresses().items():
        creation = rpc_call(
            RPC_ANSON, "eth_getTransactionByHash", [by_contract[address.lower()]["transactionHash"]]
        )
        key = paladin_call(
            "node1", "keymgr_resolveKey", [SENDERS[short], "ecdsa:secp256k1", "eth_address"]
        )
        assert creation["from"].lower() == key["verifier"]["verifier"].lower(), short
    firefly_deployed: set[str] = {
        str(op["output"]["contractLocation"]["address"]).lower()
        for op in ff_get("/api/v1/namespaces/default/operations?type=blockchain_deploy&limit=200")
        if op["status"] == "Succeeded"
    }
    assert firefly_deployed.isdisjoint(a.lower() for a in paladin_addresses().values())


@pytest.mark.parametrize("node", list(PALADIN_PORTS))
def test_the_noto_domain_is_loaded_on_every_node(deployed: dict[str, str], node: str) -> None:
    assert paladin_call(node, "domain_listDomains") == ["noto"]


def test_the_addresses_of_the_other_phases_survive_in_the_same_file(
    deployed: dict[str, str],
) -> None:
    recorded = read_addresses()
    assert "trex-factory" in recorded and "token" in recorded
    assert all(name in recorded for name in ADDRESS_NAMES.values())


def test_running_deploy_again_sends_nothing_and_restarts_no_node(
    stack: DockerStack, deployed: dict[str, str]
) -> None:
    def receipt_count() -> int:
        receipts: list[Any] = paladin_call(
            "node1", "ptx_queryTransactionReceipts", [{"limit": 500}]
        )
        return len(receipts)

    before_addresses, before_starts, before_receipts = (
        read_addresses(),
        started_at(stack),
        receipt_count(),
    )
    result = run_deploy()
    assert result.returncode == 0, result.stderr
    assert "already deployed" in result.stdout
    assert read_addresses() == before_addresses
    assert started_at(stack) == before_starts
    assert receipt_count() == before_receipts
