"""The vendored Paladin v1.0.0 artifacts in contracts/paladin/ (real files, no Docker)."""

import json
import shutil
from pathlib import Path

import pytest

from src.adapters.paladin_artifacts import (
    CONTRACTS,
    CONTRACTS_DIR,
    load_noto_private_abi,
    load_paladin_artifact,
    verify_checksums,
)
from src.core.paladin.artifacts import MAX_INIT_BYTES


def test_all_four_contracts_load_with_an_abi_and_bytecode() -> None:
    for name in CONTRACTS:
        artifact = load_paladin_artifact(name)
        assert artifact.name == name.replace("_", "-")
        assert artifact.abi and artifact.bytecode.startswith("0x")
        assert artifact.init_size > 100


def test_constructor_argument_counts_match_what_the_operator_deploys() -> None:
    expected = {"registry": 1, "noto": 0, "noto_factory": 0, "noto_factory_proxy": 2}
    for name, count in expected.items():
        constructors = [e for e in load_paladin_artifact(name).abi if e["type"] == "constructor"]
        assert len(constructors[0]["inputs"]) == count, name


def test_the_registry_is_deployed_with_false_and_each_contract_has_its_own_sender_key() -> None:
    assert json.loads(load_paladin_artifact("registry").params_json) == [False]
    senders = {name: load_paladin_artifact(name).sender for name in CONTRACTS}
    assert senders == {
        "registry": "registry.operator",
        "noto": "noto.operator",
        "noto_factory": "noto_factory.operator",
        "noto_factory_proxy": "noto_factory_proxy.operator",
    }


def test_the_proxy_needs_the_factory_and_noto_first() -> None:
    assert load_paladin_artifact("noto_factory_proxy").requires == ("noto-factory", "noto")


def test_every_init_code_fits_the_shanghai_limit() -> None:
    for name in CONTRACTS:
        assert load_paladin_artifact(name).init_size <= MAX_INIT_BYTES, name


def test_the_private_noto_abi_has_mint_transfer_and_balance_of() -> None:
    functions = {e["name"]: e for e in load_noto_private_abi() if e["type"] == "function"}
    assert [i["name"] for i in functions["mint"]["inputs"]] == ["to", "amount", "data"]
    assert [i["name"] for i in functions["transfer"]["inputs"]] == ["to", "amount", "data"]
    assert [i["name"] for i in functions["balanceOf"]["inputs"]] == ["account"]
    assert [o["name"] for o in functions["balanceOf"]["outputs"]] == [
        "totalStates",
        "totalBalance",
        "overflow",
    ]


def test_the_vendored_files_match_their_recorded_sha256() -> None:
    assert verify_checksums(CONTRACTS_DIR) == []


def test_a_changed_file_is_reported_by_name(tmp_path: Path) -> None:
    copy = tmp_path / "paladin"
    shutil.copytree(CONTRACTS_DIR, copy)
    target = copy / "INotoPrivate.json"
    target.write_bytes(target.read_bytes() + b" ")
    assert verify_checksums(copy) == ["INotoPrivate.json"]


def test_a_missing_file_is_reported_by_name(tmp_path: Path) -> None:
    copy = tmp_path / "paladin"
    shutil.copytree(CONTRACTS_DIR, copy)
    (copy / "core_v1alpha1_smartcontractdeployment_noto.yaml").unlink()
    assert verify_checksums(copy) == ["core_v1alpha1_smartcontractdeployment_noto.yaml"]


def test_an_unknown_contract_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown Paladin contract"):
        load_paladin_artifact("pente_factory")
