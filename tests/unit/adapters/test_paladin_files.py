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
