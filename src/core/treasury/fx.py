"""CAD to GBP conversion and the fixed rate table (pure).

A rate is an integer in parts per million (`580000` is 0.580000 GBP per CAD). The table is the
parsed content of `fx-rates.json`; reading the file is the adapter's job.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

from src.core.treasury.errors import AmountTooSmall, FxRateMissing, InvalidRate

RATE_SCALE = 1_000_000
PAIR = "CADGBP"

_RATE = re.compile(r"(\d+)(?:\.(\d{1,6}))?")
_DATE_KEY = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Rates:
    by_date: Mapping[int, int]  # yyyymmdd to ratePpm
    default: int | None


def parse_rate(text: str) -> int:
    """`"0.58"` to `580000`. Digits with at most 6 decimals, above zero."""
    match = _RATE.fullmatch(text.strip())
    if match is None:
        raise InvalidRate(f"{text!r} is not a rate: use digits with at most 6 decimals")
    whole, fraction = match.groups()
    ppm = int(whole) * RATE_SCALE + int((fraction or "").ljust(6, "0"))
    if ppm <= 0:
        raise InvalidRate("the rate must be above zero")
    return ppm


def format_rate(ppm: int) -> str:
    return f"{ppm // RATE_SCALE}.{ppm % RATE_SCALE:06d}"


def convert_cad_to_gbp(cad_minor: int, rate_ppm: int) -> int:
    """GBP minor units, rounded down. Same formula as `FundingRequest.settle`."""
    if cad_minor <= 0 or rate_ppm <= 0:
        raise ValueError("the amount and the rate must be above zero")
    gbp = cad_minor * rate_ppm // RATE_SCALE
    if gbp == 0:
        raise AmountTooSmall(
            f"{cad_minor} CAD minor units at {format_rate(rate_ppm)} converts to less than 0.01 GBP"
        )
    return gbp


def parse_rates(document: Mapping[str, object]) -> Rates:
    """The `CADGBP` object of `fx-rates.json`: `default` and/or `YYYY-MM-DD` keys, rates as text."""
    table = document.get(PAIR)
    if not isinstance(table, dict) or not table:
        raise InvalidRate(f"the rate table needs a non-empty {PAIR} object")
    by_date: dict[int, int] = {}
    default: int | None = None
    for key, value in table.items():
        if not isinstance(value, str):
            raise InvalidRate(f"{key}: the rate must be text such as '0.580000'")
        ppm = parse_rate(value)
        if key == "default":
            default = ppm
        elif _DATE_KEY.fullmatch(key):
            try:
                parsed = date.fromisoformat(key)
            except ValueError as exc:
                raise InvalidRate(f"{key} is not a calendar date") from exc
            by_date[parsed.year * 10000 + parsed.month * 100 + parsed.day] = ppm
        else:
            raise InvalidRate(f"{key!r} is neither 'default' nor a YYYY-MM-DD date")
    return Rates(by_date, default)


def lookup(rates: Rates, processing_date: int) -> tuple[int, Literal["dated", "default"]]:
    """The rate for the date, else the default, else `FxRateMissing` (never a guess)."""
    if processing_date in rates.by_date:
        return rates.by_date[processing_date], "dated"
    if rates.default is not None:
        return rates.default, "default"
    text = str(processing_date)
    raise FxRateMissing(f"no {PAIR} rate for {text[:4]}-{text[4:6]}-{text[6:]} and no default")
