import pytest

from src.core.treasury.errors import LedgerMismatch
from src.core.treasury.ledger import check_conservation
from src.core.treasury.request import Request, Status


def make(status: Status, cad: int = 100000, gbp: int = 0) -> Request:
    return Request(
        id="0x" + "00" * 32,
        requester="0xabc",
        amount_cad=cad,
        processing_date=20261018,
        status=status,
        amount_gbp=gbp,
        rate_ppm=580000 if gbp else 0,
    )


@pytest.mark.parametrize(
    ("requests", "cadc", "gbpc"),
    [
        ([], 0, 0),
        ([make(Status.REQUESTED)], 0, 0),
        ([make(Status.APPROVED)], 100000, 0),
        ([make(Status.REJECTED)], 0, 0),
        ([make(Status.SETTLED, gbp=58000)], 0, 58000),
        ([make(Status.REDEEMED, gbp=58000)], 0, 0),
        ([make(Status.APPROVED, 500), make(Status.SETTLED, 100000, 58000)], 500, 58000),
    ],
)
def test_the_valid_stages_conserve(requests: list[Request], cadc: int, gbpc: int) -> None:
    check_conservation(requests, cadc, gbpc)


@pytest.mark.parametrize(("cadc", "gbpc"), [(99999, 0), (100001, 0), (100000, 1)])
def test_a_supply_off_by_one_is_caught(cadc: int, gbpc: int) -> None:
    with pytest.raises(LedgerMismatch):
        check_conservation([make(Status.APPROVED)], cadc, gbpc)


def test_gbp_supply_drift_is_caught() -> None:
    with pytest.raises(LedgerMismatch, match="GBPC"):
        check_conservation([make(Status.SETTLED, gbp=58000)], 0, 57999)


def test_a_settled_request_must_follow_the_conversion_formula() -> None:
    with pytest.raises(LedgerMismatch, match="rate"):
        check_conservation([make(Status.SETTLED, gbp=58001)], 0, 58001)
