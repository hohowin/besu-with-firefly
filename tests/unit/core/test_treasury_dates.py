from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.core.treasury.dates import format_processing_date, processing_date

LONDON = ZoneInfo("Europe/London")
TOKYO = ZoneInfo("Asia/Tokyo")


def test_same_instant_is_a_different_date_in_each_zone() -> None:
    # BST: 23:30 in London, 07:30 the next day in Tokyo
    now = datetime(2026, 10, 18, 22, 30, tzinfo=UTC)
    assert processing_date(now, LONDON) == 20261018
    assert processing_date(now, TOKYO) == 20261019


def test_london_summer_time_moves_midnight() -> None:
    assert processing_date(datetime(2026, 7, 1, 23, 30, tzinfo=UTC), LONDON) == 20260702
    assert processing_date(datetime(2026, 12, 1, 23, 30, tzinfo=UTC), LONDON) == 20261201


@pytest.mark.parametrize(
    ("instant", "expected"),
    [
        (datetime(2026, 3, 29, 0, 59, tzinfo=UTC), 20260329),  # last minute of GMT
        (datetime(2026, 3, 29, 1, 0, tzinfo=UTC), 20260329),  # first minute of BST
        (datetime(2026, 10, 24, 23, 30, tzinfo=UTC), 20261025),  # BST: after local midnight
        (datetime(2026, 10, 25, 23, 30, tzinfo=UTC), 20261025),  # GMT again, still the 25th
    ],
)
def test_dates_around_the_clock_changes(instant: datetime, expected: int) -> None:
    assert processing_date(instant, LONDON) == expected


def test_a_naive_clock_is_refused() -> None:
    with pytest.raises(ValueError, match="time zone"):
        processing_date(datetime(2026, 10, 18, 12, 0), LONDON)


def test_any_aware_instant_is_accepted() -> None:
    plus_eight = timezone(timedelta(hours=8))
    assert processing_date(datetime(2026, 10, 19, 5, 0, tzinfo=plus_eight), LONDON) == 20261018


def test_format_processing_date() -> None:
    assert format_processing_date(20261018) == "2026-10-18"
