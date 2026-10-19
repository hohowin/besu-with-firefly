"""What the UI and the API show (pure): amounts as text, wallets by name, dates as ISO."""

from collections.abc import Mapping
from typing import Any

from src.core.treasury.dates import format_processing_date
from src.core.treasury.errors import FxRateMissing
from src.core.treasury.fx import PAIR, Rates, format_rate, lookup
from src.core.treasury.gateway import Balances
from src.core.treasury.ids import uuid_from_request_id
from src.core.treasury.money import format_amount
from src.core.treasury.request import Request, allowed_actions


def request_view(request: Request, names: Mapping[str, str], note: str | None) -> dict[str, Any]:
    """`names` maps a wallet address to its name; an address without a name is shown as it is."""

    def who(address: str | None) -> str | None:
        return None if address is None else names.get(address, address)

    settled = request.rate_ppm > 0
    return {
        "id": uuid_from_request_id(request.id),
        "status": request.status.name.lower(),
        "requester": who(request.requester),
        "amountCad": format_amount(request.amount_cad),
        "amountGbp": format_amount(request.amount_gbp) if settled else None,
        "rate": format_rate(request.rate_ppm) if settled else None,
        "processingDate": format_processing_date(request.processing_date),
        "approver": who(request.approver),
        "note": note,
        "actions": sorted(action.value for action in allowed_actions(request.status)),
    }


def balances_view(balances: Balances) -> dict[str, Any]:
    return {
        "balances": {
            wallet: {token: format_amount(value) for token, value in held.items()}
            for wallet, held in balances.balances.items()
        },
        "supply": {token: format_amount(value) for token, value in balances.supply.items()},
    }


def fx_view(rates: Rates, today: int) -> dict[str, Any]:
    try:
        ppm, source = lookup(rates, today)
        applies: dict[str, Any] = {
            "date": format_processing_date(today),
            "rate": format_rate(ppm),
            "source": source,
        }
    except FxRateMissing:
        applies = {"date": format_processing_date(today), "rate": None, "source": None}
    return {
        "pair": PAIR,
        "default": None if rates.default is None else format_rate(rates.default),
        "dates": {
            format_processing_date(day): format_rate(ppm)
            for day, ppm in sorted(rates.by_date.items())
        },
        "today": applies,
    }
