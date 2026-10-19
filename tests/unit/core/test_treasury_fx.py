import pytest

from src.core.treasury.errors import AmountTooSmall, FxRateMissing, InvalidRate
from src.core.treasury.fx import (
    RATE_SCALE,
    Rates,
    convert_cad_to_gbp,
    format_rate,
    lookup,
    parse_rate,
    parse_rates,
)


@pytest.mark.parametrize(
    ("text", "ppm"), [("0.58", 580000), ("0.580000", 580000), ("1", 1000000), ("0.000001", 1)]
)
def test_parse_rate_valid(text: str, ppm: int) -> None:
    assert parse_rate(text) == ppm


@pytest.mark.parametrize("text", ["0", "0.0", "-0.5", "0.5800001", "x", "", "1e-1", ".5", "1,5"])
def test_parse_rate_invalid(text: str) -> None:
    with pytest.raises(InvalidRate):
        parse_rate(text)


def test_format_rate() -> None:
    assert format_rate(580000) == "0.580000"
    assert format_rate(1) == "0.000001"


@pytest.mark.parametrize(
    ("cad", "ppm", "gbp"), [(100000, 580000, 58000), (10001, 580000, 5800), (100, RATE_SCALE, 100)]
)
def test_convert_floors(cad: int, ppm: int, gbp: int) -> None:
    assert convert_cad_to_gbp(cad, ppm) == gbp


def test_convert_rounding_to_zero_is_an_error() -> None:
    with pytest.raises(AmountTooSmall):
        convert_cad_to_gbp(1, 580000)


def test_convert_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        convert_cad_to_gbp(0, 580000)
    with pytest.raises(ValueError):
        convert_cad_to_gbp(100, 0)


DOC = {"notice": "x", "CADGBP": {"default": "0.580000", "2026-10-18": "0.581200"}}


def test_parse_rates_reads_dated_and_default() -> None:
    rates = parse_rates(DOC)
    assert rates == Rates(by_date={20261018: 581200}, default=580000)


def test_parse_rates_without_default() -> None:
    assert parse_rates({"CADGBP": {"2026-10-18": "0.5"}}) == Rates({20261018: 500000}, None)


@pytest.mark.parametrize(
    "doc",
    [
        {},
        {"CADGBP": []},
        {"CADGBP": {"2026-13-40": "0.5"}},
        {"CADGBP": {"today": "0.5"}},
        {"CADGBP": {"default": "abc"}},
        {"CADGBP": {"default": 0.58}},
        {"CADGBP": {}},
    ],
)
def test_parse_rates_rejects_bad_documents(doc: dict[str, object]) -> None:
    with pytest.raises(InvalidRate):
        parse_rates(doc)


def test_lookup_order() -> None:
    rates = parse_rates(DOC)
    assert lookup(rates, 20261018) == (581200, "dated")
    assert lookup(rates, 20261019) == (580000, "default")


def test_lookup_missing_raises_with_the_date() -> None:
    with pytest.raises(FxRateMissing, match="2026-10-18"):
        lookup(Rates({}, None), 20261018)
