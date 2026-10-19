"""The processing date (pure): the requester's local calendar date, as `yyyymmdd`.

The clock and the zone are passed in, so this does no I/O. The date is a business label, not a
trusted timestamp (TD-06).
"""

from datetime import datetime, tzinfo


def processing_date(now: datetime, zone: tzinfo) -> int:
    if now.tzinfo is None:
        raise ValueError("the clock must carry a time zone")
    local = now.astimezone(zone)
    return local.year * 10000 + local.month * 100 + local.day


def format_processing_date(value: int) -> str:
    text = str(value)
    return f"{text[:4]}-{text[4:6]}-{text[6:]}"
