import json
from pathlib import Path

from src.adapters.addresses import read_addresses, update_addresses


def test_a_missing_file_reads_as_no_addresses(tmp_path: Path) -> None:
    assert read_addresses(tmp_path / "deployed-addresses.json") == {}


def test_update_writes_the_new_addresses(tmp_path: Path) -> None:
    path = tmp_path / "deployed-addresses.json"
    update_addresses(path, {"id-factory": "0x" + "11" * 20})
    assert read_addresses(path) == {"id-factory": "0x" + "11" * 20}


def test_update_keeps_what_other_phases_wrote(tmp_path: Path) -> None:
    path = tmp_path / "deployed-addresses.json"
    update_addresses(path, {"trex-factory": "0x" + "11" * 20})
    update_addresses(path, {"paladin-registry": "0x" + "22" * 20})
    update_addresses(path, {"trex-factory": "0x" + "33" * 20})  # a later value replaces its own key
    assert read_addresses(path) == {
        "trex-factory": "0x" + "33" * 20,
        "paladin-registry": "0x" + "22" * 20,
    }


def test_the_file_is_lf_and_ends_with_a_newline(tmp_path: Path) -> None:
    path = tmp_path / "deployed-addresses.json"
    update_addresses(path, {"a": "0x1"})
    raw = path.read_bytes()
    assert raw.endswith(b"\n") and b"\r" not in raw
    assert json.loads(raw) == {"a": "0x1"}
