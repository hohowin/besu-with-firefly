"""Write the generated Paladin material to disk (adapter, I/O only).

Per node: a base config with a fresh demo mnemonic, and a self-signed TLS certificate. Plus the
Postgres init script. Everything is demo only and committed (plan D-10).
"""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from eth_account import Account

from src.core.paladin.config import NODES, base_config, postgres_init_sql

PALADIN_IMAGE = "lfdecentralizedtrust/paladin:v1.0.0"

# Makes tls.crt, tls.key and ca.crt for a node (the certificate's CN is the node name).
CertMaker = Callable[[str, Path], None]

# The gRPC transport identifies a peer by the certificate's CN (the node name), wants exactly one
# leaf certificate, and verifies it against the issuer the peer published, so each node has a
# self-signed certificate that is its own CA (Phase 0 spike).
_OPENSSL = (
    "openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 3650 "
    "-subj /CN={node} -addext subjectAltName=DNS:paladin-{node} "
    "-addext basicConstraints=critical,CA:TRUE "
    "-addext keyUsage=digitalSignature,keyCertSign "
    "-addext extendedKeyUsage=serverAuth,clientAuth "
    "-keyout /out/tls.key -out /out/tls.crt && cp /out/tls.crt /out/ca.crt"
)


def docker_cert_maker(image: str = PALADIN_IMAGE) -> CertMaker:
    """Make certificates with `openssl` inside the Paladin image (no Python dependency)."""

    def make(node: str, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        command = [
            "docker", "run", "--rm", "-v", f"{out_dir.resolve()}:/out", "--entrypoint", "sh",
            image, "-c", _OPENSSL.format(node=node),
        ]  # fmt: skip
        proc = subprocess.run(command, capture_output=True, text=True, timeout=300, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f"openssl failed for {node}: {proc.stderr.strip()[-400:]}")
        missing = [n for n in ("tls.crt", "tls.key", "ca.crt") if not (out_dir / n).is_file()]
        if missing:
            raise RuntimeError(f"openssl wrote no {', '.join(missing)} for {node}")

    return make


def new_mnemonic() -> str:
    """A fresh 12-word BIP39 phrase for a demo wallet."""
    Account.enable_unaudited_hdwallet_features()
    _account, phrase = Account.create_with_mnemonic(num_words=12)
    return str(phrase)


def seed_runtime(paladin_dir: Path, runtime_dir: Path) -> list[Path]:
    """Copy each node's base config into the runtime folder that Compose mounts.

    A config that is already there is kept: once `deploy` has written the final one (with the
    domain and registry addresses) it must not be put back to the base. Returns what was copied.
    """
    copied: list[Path] = []
    for node in NODES:
        source = paladin_dir / node / "pldconf.paladin.yaml"
        if not source.is_file():
            raise FileNotFoundError(
                f"{source} not found. Run `python scripts/stack.py init` to generate it."
            )
        target = runtime_dir / node / "pldconf.paladin.yaml"
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied.append(target)
    return copied


def write_paladin_files(paladin_dir: Path, cert_maker: CertMaker) -> list[Path]:
    """Write the config and certificates of every node and the Postgres init script.

    Anything earlier in `paladin_dir` is removed first, so nothing from a previous run lingers.
    """
    if paladin_dir.exists():
        shutil.rmtree(paladin_dir)
    written: list[Path] = []
    for node in NODES:
        config = paladin_dir / node / "pldconf.paladin.yaml"
        config.parent.mkdir(parents=True)
        config.write_text(base_config(node, new_mnemonic()), encoding="utf-8", newline="\n")
        written.append(config)
        certs = paladin_dir / node / "certs"
        cert_maker(node, certs)
        written += sorted(p for p in certs.iterdir() if p.is_file())
    init_sql = paladin_dir / "postgres-init" / "init.sql"
    init_sql.parent.mkdir(parents=True)
    init_sql.write_text(postgres_init_sql(), encoding="utf-8", newline="\n")
    written.append(init_sql)
    return written
