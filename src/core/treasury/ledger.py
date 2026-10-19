"""Conservation check (pure): the token supplies must equal what the requests say (I1, I2, I5).

CADC outstanding = the CAD of every `Approved` request. GBPC outstanding = the GBP of every
`Settled` request. A settled amount must also follow the conversion formula.
"""

from collections.abc import Iterable

from src.core.treasury.errors import LedgerMismatch
from src.core.treasury.fx import RATE_SCALE, format_rate
from src.core.treasury.request import Request, Status


def check_conservation(requests: Iterable[Request], cadc_supply: int, gbpc_supply: int) -> None:
    items = list(requests)
    for item in items:
        if item.status in (Status.SETTLED, Status.REDEEMED):
            expected = item.amount_cad * item.rate_ppm // RATE_SCALE
            if item.amount_gbp != expected:
                raise LedgerMismatch(
                    f"{item.id}: {item.amount_gbp} GBP does not follow the rate "
                    f"{format_rate(item.rate_ppm)} on {item.amount_cad} CAD (expected {expected})"
                )
    cad = sum(r.amount_cad for r in items if r.status is Status.APPROVED)
    gbp = sum(r.amount_gbp for r in items if r.status is Status.SETTLED)
    if cadc_supply != cad:
        raise LedgerMismatch(f"CADC supply is {cadc_supply}, approved requests add up to {cad}")
    if gbpc_supply != gbp:
        raise LedgerMismatch(f"GBPC supply is {gbpc_supply}, settled requests add up to {gbp}")
