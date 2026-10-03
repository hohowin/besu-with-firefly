from typing import Any

import pytest

from src.adapters.paladin_artifacts import load_paladin_artifact
from src.adapters.paladin_deploy import PaladinBootstrapError
from src.adapters.paladin_registry import register_nodes
from src.core.paladin.config import NODES
from src.core.paladin.rpc import PaladinRpcError

REGISTRY = "0x" + "99" * 20


def details_of(node: str) -> str:
    return f'{{"endpoint":"dns:///paladin-{node}:9000"}}'


class FakeRegistry:
    """A stateful stand-in for the three Paladin nodes and the EVM registry."""

    def __init__(self, fail_on: str | None = None, visible_after: int = 0) -> None:
        self.visible_after = visible_after  # queries before a new entry is indexed
        self.queries_since_change = 10_000
        self.entries: dict[str, dict[str, Any]] = {
            "root": {"name": "root", "id": "0x" + "00" * 32, "properties": {"$owner": "0xaa"}}
        }
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self.fail_on = fail_on
        self.indexed: set[str] = {"root"}

    def call(self, node: str, method: str, params: list[Any] | None = None) -> Any:
        if method == "reg_queryEntriesWithProps":
            assert node == "node1" and params is not None and params[0] == "evm-registry"
            self.queries_since_change += 1
            if self.queries_since_change <= self.visible_after:
                return [dict(e) for e in self.entries.values() if e["name"] in self.indexed]
            return [dict(e) for e in self.entries.values()]
        if method == "transport_localTransportDetails":
            return details_of(node)
        if method == "keymgr_resolveKey":
            assert params is not None and params[0] == f"registry.{node}"
            return {"verifier": {"verifier": f"0xowner-{node}"}}
        raise AssertionError(method)

    def send_and_wait(self, node: str, transaction: dict[str, Any], **_: Any) -> dict[str, Any]:
        function, data = transaction["function"], transaction["data"]
        self.sent.append((node, transaction))
        if self.fail_on == function:
            raise PaladinRpcError(f"{function} reverted")
        assert transaction["to"] == REGISTRY and transaction["type"] == "public"
        if function == "registerIdentity":
            assert node == "node1" and transaction["from"] == "registry.operator"
            assert data["parentIdentityHash"] == "0x" + "00" * 32
            self.entries[data["name"]] = {
                "name": data["name"],
                "id": "0x" + data["name"][-1] * 64,
                "properties": {"$owner": data["owner"]},
            }
            self.queries_since_change = 0
        elif function == "setIdentityProperty":
            entry = next(e for e in self.entries.values() if e["id"] == data["identityHash"])
            assert transaction["from"] == f"registry.{entry['name']}" and node == entry["name"]
            entry["properties"][data["name"]] = data["value"]
        else:
            raise AssertionError(function)
        return {"success": True}


def run(fake: FakeRegistry) -> None:
    register_nodes(
        fake,  # type: ignore[arg-type]
        load_paladin_artifact,
        REGISTRY,
        lambda _line: None,
        sleep=lambda _s: None,
        clock=iter(range(100_000)).__next__,
    )


def test_every_node_is_registered_by_node1_with_its_own_key_as_owner() -> None:
    fake = FakeRegistry()
    run(fake)
    registrations = [t for _n, t in fake.sent if t["function"] == "registerIdentity"]
    assert [t["data"]["name"] for t in registrations] == list(NODES)
    assert [t["data"]["owner"] for t in registrations] == [f"0xowner-{n}" for n in NODES]


def test_every_node_sets_its_own_transport_details_on_its_own_node() -> None:
    fake = FakeRegistry()
    run(fake)
    for node in NODES:
        properties = fake.entries[node]["properties"]
        assert properties["transport.grpc"] == details_of(node)
    setters = [(n, t["from"]) for n, t in fake.sent if t["function"] == "setIdentityProperty"]
    assert setters == [(n, f"registry.{n}") for n in NODES]


def test_each_transaction_carries_the_registry_abi() -> None:
    fake = FakeRegistry()
    run(fake)
    abi = load_paladin_artifact("registry").abi
    assert all(t["abi"] == abi for _n, t in fake.sent)


def test_a_second_run_sends_nothing() -> None:
    fake = FakeRegistry()
    run(fake)
    sent = len(fake.sent)
    run(fake)
    assert len(fake.sent) == sent == 6


def test_only_the_missing_part_is_sent_after_an_interrupted_run() -> None:
    fake = FakeRegistry()
    run(fake)
    del fake.entries["node3"]["properties"]["transport.grpc"]
    fake.sent.clear()
    run(fake)
    assert [t["function"] for _n, t in fake.sent] == ["setIdentityProperty"]


def test_a_failed_registration_stops_the_run_and_names_the_node() -> None:
    fake = FakeRegistry(fail_on="registerIdentity")
    with pytest.raises(PaladinBootstrapError, match=r"node1.*registerIdentity reverted"):
        run(fake)
    assert len(fake.sent) == 1


def test_a_new_entry_that_the_node_has_not_indexed_yet_is_waited_for() -> None:
    """node1 indexes registry events as blocks arrive, so a fresh entry shows up a moment later."""
    fake = FakeRegistry(visible_after=3)
    fake.indexed = {"root"}

    original = fake.call

    def call(node: str, method: str, params: list[Any] | None = None) -> Any:
        result = original(node, method, params)
        if method == "reg_queryEntriesWithProps" and fake.queries_since_change > fake.visible_after:
            fake.indexed = set(fake.entries)
        return result

    fake.call = call  # type: ignore[method-assign]
    run(fake)
    assert all("transport.grpc" in fake.entries[n]["properties"] for n in NODES)


def test_an_entry_that_never_shows_up_is_an_error_naming_it() -> None:
    fake = FakeRegistry(visible_after=10**9)
    with pytest.raises(PaladinBootstrapError, match=r"node1.*not in the registry index"):
        run(fake)
