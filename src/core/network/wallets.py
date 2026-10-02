"""Demo wallet model and checks (pure computation, no I/O)."""

from dataclasses import dataclass
from typing import Any

from eth_account import Account

DEMO_NOTICE = (
    "DEMO ONLY. Throwaway keys for a local network with no real value, committed on purpose "
    "(plan D-10). Never reuse them anywhere else."
)


@dataclass(frozen=True)
class Wallet:
    name: str
    address: str  # 0x plus 40 lowercase hex characters
    private_key: str  # 0x plus 64 hex characters


def derive_address(private_key: str) -> str:
    """Return the lowercase Ethereum address for a private key."""
    key = private_key.strip().removeprefix("0x")
    try:
        account = Account.from_key("0x" + key)
    except ValueError as error:
        raise ValueError(f"not a valid private key: {error}") from error
    return str(account.address).lower()


def verify_wallet(wallet: Wallet) -> None:
    """Raise if the wallet's address is not the one derived from its private key."""
    derived = derive_address(wallet.private_key)
    if derived != wallet.address.lower():
        raise ValueError(
            f"address {wallet.address} of wallet {wallet.name!r} does not match its key ({derived})"
        )


def build_wallets_document(wallets: list[Wallet]) -> dict[str, Any]:
    """The content of `wallets.json`. Validates names and that every address matches its key."""
    names = [w.name for w in wallets]
    if any(not name.strip() for name in names):
        raise ValueError("every wallet needs a non-empty name")
    if len(names) != len(set(names)):
        raise ValueError(f"wallet names must be unique, got {names}")
    for wallet in wallets:
        verify_wallet(wallet)
    return {
        "notice": DEMO_NOTICE,
        "wallets": [
            {"name": w.name, "address": w.address, "privateKey": w.private_key} for w in wallets
        ],
    }


def account_addresses(document: dict[str, Any]) -> dict[str, str]:
    """Wallet name to address, from the content of `wallets.json`."""
    wallets = document.get("wallets")
    if not wallets:
        raise ValueError("the wallets document has no wallets")
    return {str(w["name"]): str(w["address"]).lower() for w in wallets}


def wallet_private_key(document: dict[str, Any], name: str) -> str:
    """The private key of the wallet called `name`, from the content of `wallets.json`."""
    for wallet in document.get("wallets", []):
        if wallet["name"] == name:
            return str(wallet["privateKey"])
    raise ValueError(f"no wallet called {name!r}")
