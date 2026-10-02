"""Write the generated FireFly config and signer keystores to disk (adapter, I/O only)."""

import shutil
from pathlib import Path

from src.core.firefly.config import core_config, evmconnect_config, signer_config
from src.core.firefly.keystore import keystore_files
from src.core.network.wallets import Wallet


def write_firefly_files(firefly_dir: Path, wallets: list[Wallet]) -> list[Path]:
    """Write `core.yml`, `evmconnect.yml`, `signer.yml` and `signer-data/` into `firefly_dir`.

    The default signing key is the wallet named `admin`. Any earlier `signer-data/` is removed
    first, so keystores of replaced wallets do not linger.
    """
    admin = next((w for w in wallets if w.name == "admin"), None)
    if admin is None:
        raise ValueError("FireFly needs a wallet named 'admin' as its default key")
    signer_data = firefly_dir / "signer-data"
    if signer_data.exists():
        shutil.rmtree(signer_data)
    contents = {
        firefly_dir / "core.yml": core_config(admin.address),
        firefly_dir / "evmconnect.yml": evmconnect_config(),
        firefly_dir / "signer.yml": signer_config(),
    }
    for relative, text in keystore_files(wallets).items():
        contents[signer_data / relative] = text
    for path, text in contents.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return list(contents)
