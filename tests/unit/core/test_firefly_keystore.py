import json
import tomllib

import pytest
from eth_account import Account

from src.core.firefly.keystore import DEMO_PASSWORD, keystore_files
from src.core.network.wallets import Wallet, derive_address

# The well-known Ethereum test key (private key 1) and a second throwaway one.
WALLETS = [
    Wallet("admin", derive_address("0x" + "00" * 31 + "01"), "0x" + "00" * 31 + "01"),
    Wallet("anson", derive_address("0x" + "00" * 31 + "02"), "0x" + "00" * 31 + "02"),
]


def test_each_wallet_gets_a_keystore_named_by_its_address_without_0x() -> None:
    files = keystore_files(WALLETS)
    for wallet in WALLETS:
        stem = wallet.address.removeprefix("0x")
        assert f"keystore/{stem}" in files
        assert f"keystore/{stem}.toml" in files
    assert "password" in files


def test_the_keystore_decrypts_with_the_shared_password_to_the_wallet_key() -> None:
    files = keystore_files(WALLETS)
    password = files["password"].strip()
    assert password == DEMO_PASSWORD
    for wallet in WALLETS:
        keystore = json.loads(files[f"keystore/{wallet.address.removeprefix('0x')}"])
        key = Account.decrypt(keystore, password)
        assert "0x" + key.hex() == wallet.private_key


def test_the_toml_points_the_signer_at_the_mounted_key_and_password() -> None:
    files = keystore_files(WALLETS)
    stem = WALLETS[0].address.removeprefix("0x")
    toml = tomllib.loads(files[f"keystore/{stem}.toml"])
    assert toml["signing"]["type"] == "file-based-signer"
    assert toml["signing"]["key-file"] == f"/data/keystore/{stem}"
    assert toml["signing"]["password-file"] == "/data/password"


def test_a_wallet_whose_address_does_not_match_its_key_is_rejected() -> None:
    bad = Wallet("admin", "0x" + "11" * 20, WALLETS[0].private_key)
    with pytest.raises(ValueError, match="does not match"):
        keystore_files([bad])
