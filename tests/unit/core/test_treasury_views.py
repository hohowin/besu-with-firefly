from src.core.treasury.fx import Rates
from src.core.treasury.gateway import Balances
from src.core.treasury.ids import request_id_from_uuid
from src.core.treasury.request import Request, Status
from src.core.treasury.views import balances_view, fx_view, request_view

UUID = "123e4567-e89b-12d3-a456-426614174000"
NAMES = {"0xa1": "ldn", "0xa2": "tor"}


def settled() -> Request:
    return Request(
        id=request_id_from_uuid(UUID),
        requester="0xa1",
        amount_cad=100000,
        processing_date=20261018,
        status=Status.SETTLED,
        amount_gbp=58000,
        rate_ppm=580000,
        approver="0xa2",
    )


def test_a_settled_request_shows_amounts_rate_date_and_names() -> None:
    view = request_view(settled(), NAMES, None)
    assert view == {
        "id": UUID,
        "status": "settled",
        "requester": "ldn",
        "amountCad": "1000.00",
        "amountGbp": "580.00",
        "rate": "0.580000",
        "processingDate": "2026-10-18",
        "approver": "tor",
        "note": None,
        "actions": ["redeem"],
    }


def test_an_open_request_has_no_gbp_rate_or_approver_yet() -> None:
    open_request = Request(
        id=request_id_from_uuid(UUID),
        requester="0xa1",
        amount_cad=5,
        processing_date=20261018,
        status=Status.REQUESTED,
    )
    view = request_view(open_request, NAMES, "waiting")
    assert view["amountGbp"] is None and view["rate"] is None and view["approver"] is None
    assert view["note"] == "waiting"
    assert view["actions"] == ["approve", "reject"]


def test_an_unknown_address_is_shown_as_it_is() -> None:
    view = request_view(settled(), {}, None)
    assert view["requester"] == "0xa1"


def test_balances_are_formatted_as_amounts() -> None:
    view = balances_view(Balances({"ldn": {"cadc": 0, "gbpc": 58000}}, {"cadc": 0, "gbpc": 58000}))
    assert view == {
        "balances": {"ldn": {"cadc": "0.00", "gbpc": "580.00"}},
        "supply": {"cadc": "0.00", "gbpc": "580.00"},
    }


def test_fx_view_lists_the_table_and_the_rate_that_applies_today() -> None:
    rates = Rates({20261018: 581200}, 580000)
    assert fx_view(rates, 20261018) == {
        "pair": "CADGBP",
        "default": "0.580000",
        "dates": {"2026-10-18": "0.581200"},
        "today": {"date": "2026-10-18", "rate": "0.581200", "source": "dated"},
    }
    assert fx_view(rates, 20261019)["today"] == {
        "date": "2026-10-19",
        "rate": "0.580000",
        "source": "default",
    }


def test_fx_view_says_so_when_no_rate_applies() -> None:
    view = fx_view(Rates({}, None), 20261018)
    assert view["default"] is None
    assert view["today"] == {"date": "2026-10-18", "rate": None, "source": None}
