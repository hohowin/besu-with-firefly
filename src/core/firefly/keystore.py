"""Build the FireFly signer's file keystore from the demo wallets (pure, no I/O).

The signer reads one Ethereum keystore JSON per key, a `.toml` that points at it, and a shared
password file (Phase 0 spike, Risk 1). Everything is demo only and committed (plan D-10).
"""

import json

from eth_account import Account

from src.core.network.wallets import Wallet, verify_wallet

DEMO_PASSWORD = "correcthorsebatterystaple"
MOUNT = "/data"  # where Compose mounts `firefly/signer-data` inside the signer container
# scrypt cost is low on purpose: these keys are public demo keys, and the signer reads every
# keystore at start-up.
_SCRYPT_N = 4096

_TOML = """\
[metadata]
description = "File based configuration"

[signing]
type = "file-based-signer"
key-file = "{mount}/keystore/{stem}"
password-file = "{mount}/password"
"""


def keystore_files(wallets: list[Wallet], password: str = DEMO_PASSWORD) -> dict[str, str]:
    """Relative path (below `signer-data/`) to file content for every wallet plus the password."""
    files: dict[str, str] = {}
    for wallet in wallets:
        verify_wallet(wallet)
        stem = wallet.address.lower().removeprefix("0x")
        private_key = bytes.fromhex(wallet.private_key.removeprefix("0x"))
        keystore = Account.encrypt(private_key, password, kdf="scrypt", iterations=_SCRYPT_N)
        files[f"keystore/{stem}"] = json.dumps(keystore)
        files[f"keystore/{stem}.toml"] = _TOML.format(mount=MOUNT, stem=stem)
    files["password"] = password
    return files
