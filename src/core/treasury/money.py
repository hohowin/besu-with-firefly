"""Money in minor units (pure): CAD and GBP both count in hundredths, so 1000.00 is 100000.

No floating point anywhere (TR-NFR-01): amounts are parsed from text with a strict pattern.
"""

import re

from src.core.treasury.errors import InvalidAmount

DECIMALS = 2
MAX_AMOUNT_MINOR = 100_000_000  # CAD 1,000,000.00, the default cap per request (Q8)

_AMOUNT = re.compile(r"(\d+)(?:\.(\d{1,2}))?")


def parse_amount(text: str, max_minor: int = MAX_AMOUNT_MINOR) -> int:
    """`"1000.00"` to `100000`. Digits with at most 2 decimals, above zero, within the cap."""
    match = _AMOUNT.fullmatch(text.strip())
    if match is None:
        raise InvalidAmount(f"{text!r} is not an amount: use digits with at most 2 decimals")
    whole, fraction = match.groups()
    minor = int(whole) * 100 + int((fraction or "").ljust(DECIMALS, "0"))
    if minor <= 0:
        raise InvalidAmount("the amount must be above zero")
    if minor > max_minor:
        raise InvalidAmount(f"{text.strip()} is above the cap of {format_amount(max_minor)}")
    return minor


def format_amount(minor: int) -> str:
    """`100000` to `"1000.00"`."""
    if minor < 0:
        raise ValueError(f"an amount cannot be negative, got {minor}")
    return f"{minor // 100}.{minor % 100:02d}"
