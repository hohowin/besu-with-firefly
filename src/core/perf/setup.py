"""What the benchmark wallets still need (pure)."""

from src.core.trex.amounts import to_base_units


def coins_missing(balance: int | str, target_coins: int) -> int:
    """Base units to mint so a wallet holding `balance` base units reaches `target_coins` COIN.

    Zero when it already holds that much or more: a wallet is topped up, never drained.
    """
    target = to_base_units(target_coins)
    return max(0, target - int(balance))
