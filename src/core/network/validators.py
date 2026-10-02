"""Validator address helpers (pure, no I/O)."""

import re
from collections.abc import Iterable

_ADDRESS = re.compile(r"[0-9a-f]{40}")


def normalize_address(address: str) -> str:
    """Return `0x` plus 40 lowercase hex characters."""
    body = address.strip().lower().removeprefix("0x")
    if not _ADDRESS.fullmatch(body):
        raise ValueError(f"an address must be 40 hex characters, got {address!r}")
    return "0x" + body


def sort_validators(addresses: Iterable[str]) -> list[str]:
    """Normalize and sort addresses ascending, so validator numbering is stable."""
    normalized = [normalize_address(a) for a in addresses]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"duplicate validator addresses in {normalized}")
    return sorted(normalized)


def extra_data_lists_all(extra_data: str, addresses: Iterable[str]) -> bool:
    """True when every address appears in the genesis `extraData` hex string."""
    haystack = extra_data.lower()
    return all(normalize_address(a).removeprefix("0x") in haystack for a in addresses)
