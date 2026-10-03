from pathlib import Path
from typing import Any

import pytest

from src.adapters.paladin import TransactionFailed
from src.adapters.paladin_artifacts import CONTRACTS_DIR, load_paladin_artifact
from src.adapters.paladin_deploy import (
    PaladinBootstrapError,
    deploy_contracts,
    deploy_paladin,
    write_runtime_configs,
)
from src.core.paladin.bootstrap import ADDRESS_NAMES, initialize_call_data
from src.core.paladin.config import NODES

BASE = "nodeName: {node}\nlog:\n  level: info\n"
CODE = "0x6080" + "00" * 100


def address_of(index: int) -> str:
    return "0x" + f"{index:02x}" * 20


class FakeClient:
    """A stand-in for the Paladin client: deploys get addresses 01.., domains load on restart."""

    def __init__(self, fail_at: str | None = None, domains_after_restart: bool = True) -> None:
        self.sent: list[dict[str, Any]] = []
        self.fail_at = fail_at
        self.has_domain: dict[str, bool] = {node: False for node in NODES}
        self.restarted: set[str] = set()
        self.domains_after_restart = domains_after_restart

    def send_and_wait(self, node: str, transaction: dict[str, Any], **_: Any) -> dict[str, Any]:
        assert node == "node1"
        self.sent.append(transaction)
        if self.fail_at and len(self.sent) == self.fail_at_index():
            raise TransactionFailed("tx", "reverted")
        return {"id": "tx", "success": True, "contractAddress": address_of(len(self.sent))}

    def fail_at_index(self) -> int:
        return ["registry", "noto", "noto_factory", "noto_factory_proxy"].index(
            self.fail_at or ""
        ) + 1

    def call(self, node: str, method: str, params: list[Any] | None = None) -> Any:
        assert method == "domain_listDomains"
        if node in self.restarted and self.domains_after_restart:
            self.has_domain[node] = True
        return ["noto"] if self.has_domain[node] else []


def code_everywhere(_address: str) -> str:
    return CODE


def source_dir(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    for node in NODES:
        (source / node).mkdir(parents=True)
        (source / node / "pldconf.paladin.yaml").write_text(
            BASE.format(node=node), encoding="utf-8"
        )
    return source


def run_contracts(
    client: FakeClient, existing: dict[str, str] | None = None, code_at: Any = code_everywhere
) -> tuple[dict[str, str], list[dict[str, str]]]:
    saved: list[dict[str, str]] = []
    result = deploy_contracts(
        client,  # type: ignore[arg-type]
        load_paladin_artifact,
        existing or {},
        code_at,
        lambda updates: saved.append(dict(updates)),
        lambda _line: None,
    )
    return result, saved


def test_the_four_contracts_are_deployed_by_node1_in_the_operators_order() -> None:
    client = FakeClient()
    addresses, _saved = run_contracts(client)
    assert [t["from"] for t in client.sent] == [
        "registry.operator",
        "noto.operator",
        "noto_factory.operator",
        "noto_factory_proxy.operator",
    ]
    assert all(t["type"] == "public" for t in client.sent)
    assert addresses == {
        "registry": address_of(1),
        "noto": address_of(2),
        "noto_factory": address_of(3),
        "noto_factory_proxy": address_of(4),
    }


def test_each_deployment_carries_the_abi_the_bytecode_and_its_constructor_data() -> None:
    client = FakeClient()
    run_contracts(client)
    registry, noto, factory, proxy = client.sent
    assert registry["data"] == [False] and noto["data"] == {} and factory["data"] == {}
    assert registry["bytecode"] == load_paladin_artifact("registry").bytecode
    assert registry["abi"] == load_paladin_artifact("registry").abi
    assert proxy["data"] == [address_of(3), initialize_call_data(address_of(2))]


def test_the_addresses_are_saved_under_paladin_names_after_every_contract() -> None:
    _result, saved = run_contracts(FakeClient())
    assert [len(s) for s in saved] == [1, 1, 1, 1]
    assert saved[0] == {ADDRESS_NAMES["registry"]: address_of(1)}
    assert saved[3] == {ADDRESS_NAMES["noto_factory_proxy"]: address_of(4)}


def test_contracts_that_exist_with_code_are_skipped() -> None:
    client = FakeClient()
    existing = {ADDRESS_NAMES["registry"]: address_of(9), ADDRESS_NAMES["noto"]: address_of(8)}
    addresses, _ = run_contracts(client, existing)
    assert [t["from"] for t in client.sent] == [
        "noto_factory.operator",
        "noto_factory_proxy.operator",
    ]
    assert addresses["registry"] == address_of(9) and addresses["noto"] == address_of(8)


def test_an_existing_address_without_code_is_deployed_again() -> None:
    client = FakeClient()
    existing = {ADDRESS_NAMES["registry"]: address_of(9)}
    run_contracts(client, existing, code_at=lambda a: "0x" if a == address_of(9) else CODE)
    assert len(client.sent) == 4


def test_a_failed_deployment_stops_the_run_and_names_the_contract() -> None:
    client = FakeClient(fail_at="noto_factory")
    with pytest.raises(PaladinBootstrapError, match=r"noto_factory.*reverted") as raised:
        run_contracts(client)
    assert raised.value.step == "noto_factory"
    assert len(client.sent) == 3  # nothing after the failure was sent


def test_a_deployment_without_code_on_chain_is_an_error() -> None:
    with pytest.raises(PaladinBootstrapError, match=r"registry.*no code"):
        run_contracts(FakeClient(), code_at=lambda _a: "0x")


def test_code_over_the_size_limit_is_an_error() -> None:
    too_big = "0x" + "00" * 24_577
    with pytest.raises(PaladinBootstrapError, match=r"registry.*24577.*24576"):
        run_contracts(FakeClient(), code_at=lambda _a: too_big)


def test_the_final_config_of_every_node_is_its_base_plus_the_two_blocks(tmp_path: Path) -> None:
    source, runtime = source_dir(tmp_path), tmp_path / "runtime"
    addresses = {"registry": address_of(1), "noto_factory_proxy": address_of(4)}
    changed = write_runtime_configs(source, runtime, addresses)
    assert changed == list(NODES)
    for node in NODES:
        text = (runtime / node / "pldconf.paladin.yaml").read_text(encoding="utf-8")
        assert text.startswith(BASE.format(node=node))
        assert f"registryAddress: {address_of(4)}" in text
        assert f"contractAddress: {address_of(1)}" in text


def test_writing_the_same_configs_again_changes_nothing(tmp_path: Path) -> None:
    source, runtime = source_dir(tmp_path), tmp_path / "runtime"
    addresses = {"registry": address_of(1), "noto_factory_proxy": address_of(4)}
    write_runtime_configs(source, runtime, addresses)
    assert write_runtime_configs(source, runtime, addresses) == []


def test_new_addresses_rewrite_the_configs(tmp_path: Path) -> None:
    source, runtime = source_dir(tmp_path), tmp_path / "runtime"
    write_runtime_configs(
        source, runtime, {"registry": address_of(1), "noto_factory_proxy": address_of(4)}
    )
    changed = write_runtime_configs(
        source, runtime, {"registry": address_of(5), "noto_factory_proxy": address_of(4)}
    )
    assert changed == list(NODES)


def orchestrate(
    tmp_path: Path, client: FakeClient, existing: dict[str, str] | None = None
) -> tuple[list[str], dict[str, str]]:
    restarted: list[str] = []

    def restart(container: str) -> None:
        restarted.append(container)
        client.restarted.add(container.removeprefix("paladin-"))

    result = deploy_paladin(
        client,  # type: ignore[arg-type]
        load=load_paladin_artifact,
        source=source_dir(tmp_path) if not (tmp_path / "source").exists() else tmp_path / "source",
        runtime=tmp_path / "runtime",
        existing=existing or {},
        code_at=code_everywhere,
        save=lambda _updates: None,
        restart=restart,
        log=lambda _line: None,
        sleep=lambda _s: None,
        clock=iter(range(100_000)).__next__,
    )
    return restarted, result


def test_deploy_paladin_deploys_writes_restarts_and_waits_for_the_domain(tmp_path: Path) -> None:
    client = FakeClient()
    restarted, result = orchestrate(tmp_path, client)
    assert sorted(restarted) == ["paladin-node1", "paladin-node2", "paladin-node3"]
    assert all(client.has_domain.values())
    assert result["noto_factory_proxy"] == address_of(4)


def test_a_second_run_sends_nothing_and_restarts_nothing(tmp_path: Path) -> None:
    client = FakeClient()
    _first, addresses = orchestrate(tmp_path, client)
    existing = {ADDRESS_NAMES[k]: v for k, v in addresses.items()}
    sent_before = len(client.sent)
    restarted, _ = orchestrate(tmp_path, client, existing)
    assert restarted == []
    assert len(client.sent) == sent_before


def test_a_node_whose_domain_is_not_loaded_is_restarted_even_if_its_config_is_final(
    tmp_path: Path,
) -> None:
    """An earlier run was interrupted after writing the configs but before restarting."""
    client = FakeClient()
    _first, addresses = orchestrate(tmp_path, client)
    existing = {ADDRESS_NAMES[k]: v for k, v in addresses.items()}
    client.has_domain["node3"] = False
    client.restarted.discard("node3")
    restarted, _ = orchestrate(tmp_path, client, existing)
    assert restarted == ["paladin-node3"]


def test_a_domain_that_never_loads_is_an_error_naming_the_node(tmp_path: Path) -> None:
    client = FakeClient(domains_after_restart=False)
    with pytest.raises(PaladinBootstrapError, match=r"node1.*domain"):
        orchestrate(tmp_path, client)


def test_the_vendored_artifacts_are_where_the_loader_expects_them() -> None:
    assert (CONTRACTS_DIR / "core_v1alpha1_smartcontractdeployment_registry.yaml").is_file()
