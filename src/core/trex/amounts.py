"""COIN amounts (pure). The token has 18 decimals, so the chain counts in base units."""

from src.core.trex.plan import COIN_DECIMALS

COIN_UNITS: int = 10**COIN_DECIMALS
MINT_AMOUNT = 1000  # whole COIN minted to Anson once, the initial supply


def to_base_units(coins: int) -> int:
    """Whole COIN to base units."""
    if coins < 0:
        raise ValueError(f"an amount cannot be negative, got {coins}")
    return coins * COIN_UNITS


def from_base_units(raw: int | str) -> int:
    """Base units (an integer, or the string FireFly returns) to whole COIN."""
    value = int(raw)
    if value % COIN_UNITS != 0:
        raise ValueError(f"{value} base units is not a whole number of COIN")
    return value // COIN_UNITS


def mint_needed(total_supply: int | str) -> bool:
    """Mint until the total supply reaches the initial supply. Transfers do not change the
    supply, so this stays false afterwards and a second run mints nothing."""
    return int(total_supply) < to_base_units(MINT_AMOUNT)
