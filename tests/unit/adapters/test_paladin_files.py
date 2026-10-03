from pathlib import Path

from eth_account.hdaccount.mnemonic import Mnemonic
from eth_account.types import Language

from src.adapters.paladin_files import write_paladin_files
from src.core.paladin.config import NODES, postgres_init_sql
from tests.support.besu_fake import fake_cert_maker


def phrases(root: Path) -> list[str]:
    found = []
    for node in NODES:
        text = (root / node / "pldconf.paladin.yaml").read_text(encoding="utf-8")
        found.append(text.split('inline: "')[1].split('"')[0])
    return found


def test_each_node_gets_a_config_and_a_certificate_folder(tmp_path: Path) -> None:
    files = write_paladin_files(tmp_path, fake_cert_maker())
    for node in NODES:
        assert (tmp_path / node / "pldconf.paladin.yaml").is_file()
        names = {p.name for p in (tmp_path / node / "certs").iterdir()}
        assert names == {"tls.crt", "tls.key", "ca.crt"}
    init_sql = (tmp_path / "postgres-init" / "init.sql").read_text(encoding="utf-8")
    assert init_sql == postgres_init_sql()
    assert all(path.is_file() for path in files)


def test_the_certificate_of_each_node_is_made_for_that_node(tmp_path: Path) -> None:
    write_paladin_files(tmp_path, fake_cert_maker())
    for node in NODES:
        assert (tmp_path / node / "certs" / "tls.crt").read_text("utf-8") == f"CERT for {node}\n"


def test_the_three_mnemonics_are_valid_and_different(tmp_path: Path) -> None:
    write_paladin_files(tmp_path, fake_cert_maker())
    found = phrases(tmp_path)
    assert len(set(found)) == 3
    for phrase in found:
        assert len(phrase.split()) == 12
        assert Mnemonic(Language.ENGLISH).is_mnemonic_valid(phrase)


def test_files_use_lf_line_endings(tmp_path: Path) -> None:
    write_paladin_files(tmp_path, fake_cert_maker())
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert b"\r" not in path.read_bytes(), path


def test_writing_again_replaces_everything_including_the_mnemonics(tmp_path: Path) -> None:
    write_paladin_files(tmp_path, fake_cert_maker())
    before = phrases(tmp_path)
    stale = tmp_path / "node1" / "old-file"
    stale.write_text("x", encoding="utf-8")
    write_paladin_files(tmp_path, fake_cert_maker())
    assert phrases(tmp_path) != before
    assert not stale.exists()


def test_the_runtime_folder_is_seeded_from_the_committed_base_config(tmp_path: Path) -> None:
    from src.adapters.paladin_files import seed_runtime

    source, runtime = tmp_path / "source", tmp_path / "runtime"
    write_paladin_files(source, fake_cert_maker())
    copied = seed_runtime(source, runtime)
    assert len(copied) == 3
    for node in NODES:
        base = (source / node / "pldconf.paladin.yaml").read_bytes()
        assert (runtime / node / "pldconf.paladin.yaml").read_bytes() == base


def test_seeding_never_overwrites_a_config_that_deploy_has_written(tmp_path: Path) -> None:
    from src.adapters.paladin_files import seed_runtime

    source, runtime = tmp_path / "source", tmp_path / "runtime"
    write_paladin_files(source, fake_cert_maker())
    seed_runtime(source, runtime)
    final = runtime / "node1" / "pldconf.paladin.yaml"
    final.write_text("final config with the domain\n", encoding="utf-8")
    assert seed_runtime(source, runtime) == []
    assert final.read_text(encoding="utf-8") == "final config with the domain\n"


def test_seeding_without_the_generated_material_says_to_run_init(tmp_path: Path) -> None:
    import pytest

    from src.adapters.paladin_files import seed_runtime

    with pytest.raises(FileNotFoundError, match="stack.py init"):
        seed_runtime(tmp_path / "missing", tmp_path / "runtime")
