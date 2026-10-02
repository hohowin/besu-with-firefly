"""init_network with a fake generator, so no Docker is needed."""

import json
from pathlib import Path

import pytest

from src.adapters.besu_config import (
    AlreadyInitialisedError,
    GenerationError,
    init_network,
)
from src.core.network.enode import NetworkAddressing
from tests.support.besu_fake import fake_generator


def test_init_writes_the_expected_layout(tmp_path: Path) -> None:
    result = init_network(tmp_path, generator=fake_generator())
    assert (tmp_path / "genesis.json").is_file()
    assert (tmp_path / "static-nodes.json").is_file()
    assert (tmp_path / "README.md").is_file()
    for number in (1, 2, 3, 4):
        folder = tmp_path / "validator-keys" / f"validator-{number}"
        assert {p.name for p in folder.iterdir()} == {"key", "key.pub", "address.txt"}
    assert len(result.validator_addresses) == 4


def test_validators_are_numbered_by_sorted_address(tmp_path: Path) -> None:
    result = init_network(tmp_path, generator=fake_generator())
    assert result.validator_addresses == sorted(result.validator_addresses)
    for number, address in enumerate(result.validator_addresses, start=1):
        text = (tmp_path / "validator-keys" / f"validator-{number}" / "address.txt").read_text(
            encoding="utf-8"
        )
        assert text.strip() == address


def test_static_nodes_match_the_key_files_and_the_fixed_ips(tmp_path: Path) -> None:
    init_network(tmp_path, generator=fake_generator())
    nodes = json.loads((tmp_path / "static-nodes.json").read_text(encoding="utf-8"))
    addressing = NetworkAddressing()
    assert len(nodes) == 4
    for number, enode in enumerate(nodes, start=1):
        pub = (tmp_path / "validator-keys" / f"validator-{number}" / "key.pub").read_text(
            encoding="utf-8"
        )
        assert enode == f"enode://{pub.strip().removeprefix('0x')}@{addressing.validator_ip(number)}:30303"


def test_files_use_lf_line_endings(tmp_path: Path) -> None:
    init_network(tmp_path, generator=fake_generator())
    for name in ("static-nodes.json", "README.md"):
        assert b"\r" not in (tmp_path / name).read_bytes()


def test_readme_marks_the_keys_as_demo_only(tmp_path: Path) -> None:
    init_network(tmp_path, generator=fake_generator())
    text = (tmp_path / "README.md").read_text(encoding="utf-8").lower()
    assert "demo" in text and "never reuse" in text


def test_second_run_without_force_fails_and_changes_nothing(tmp_path: Path) -> None:
    init_network(tmp_path, generator=fake_generator(seed=1))
    before = (tmp_path / "static-nodes.json").read_bytes()
    with pytest.raises(AlreadyInitialisedError, match="--force"):
        init_network(tmp_path, generator=fake_generator(seed=2))
    assert (tmp_path / "static-nodes.json").read_bytes() == before


def test_force_regenerates_and_removes_old_validator_keys(tmp_path: Path) -> None:
    init_network(tmp_path, generator=fake_generator(seed=1))
    before = (tmp_path / "static-nodes.json").read_bytes()
    init_network(tmp_path, generator=fake_generator(seed=2), force=True)
    assert (tmp_path / "static-nodes.json").read_bytes() != before
    assert len(list((tmp_path / "validator-keys").iterdir())) == 4


def test_generator_output_missing_an_address_in_extra_data_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(GenerationError, match="extraData"):
        init_network(tmp_path, generator=fake_generator(omit_from_extra_data=True))
    assert not (tmp_path / "genesis.json").exists()


def test_generator_producing_the_wrong_number_of_validators_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(GenerationError, match="expected 4"):
        init_network(tmp_path, generator=fake_generator(count=3))
    assert not (tmp_path / "genesis.json").exists()
