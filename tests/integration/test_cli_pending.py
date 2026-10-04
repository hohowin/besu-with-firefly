"""A write whose answer never arrives is reported as pending, never as done (UC-11)."""

import json
from typing import Any

import pytest

from src.adapters.docker_stack import REPO_ROOT
from src.adapters.ff_cli import main
from src.adapters.firefly import FireflyClient, http_transport
from src.core.trex.amounts import to_base_units
from tests.support.firefly import ff_get, ff_post
from tests.support.polling import wait_for

pytestmark = pytest.mark.integration

NS = "/api/v1/namespaces/default"


def balance(address: str) -> int:
    answer = ff_post(f"{NS}/apis/coin/query/balanceOf", {"input": {"_userAddress": address}})
    return int(answer["output"])


def address_of(name: str) -> str:
    document = json.loads((REPO_ROOT / "network-config" / "wallets.json").read_text("utf-8"))
    return str(next(w["address"] for w in document["wallets"] if w["name"] == name))


def test_a_write_sent_without_an_answer_exits_three_and_later_lands(
    deployed: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    real = http_transport()

    def answer_never_arrives(method: str, path: str, body: Any = None) -> tuple[int, Any]:
        result = real(method, path, body)  # FireFly gets and handles the request ...
        if "/invoke/" in path:
            raise TimeoutError("timed out")  # ... but the caller never sees the answer
        return result

    beatrice = address_of("beatrice")
    before = balance(beatrice)
    code = main(
        ["invoke", "transfer", "--contract", "coin", "--as", "anson", "--input", "_to=@beatrice",
         "--input", f"_amount={to_base_units(1)}"],
        port=FireflyClient(answer_never_arrives, sleep=lambda _s: None),
    )  # fmt: skip
    captured = capsys.readouterr()
    assert code == 3
    assert captured.err.startswith("pending: ") and "may or may not" in captured.err
    assert "sent" not in captured.out and "error:" not in captured.err

    # Unknown is not failed: the write did land, and the developer can see it with `tx`.
    wait_for(
        lambda: balance(beatrice) == before + to_base_units(1),
        describe="the transfer to land",
    )
    operation = ff_get(f"{NS}/operations?type=blockchain_invoke&limit=1")[0]
    assert main(["tx", operation["id"]]) == 0
    assert "status     Succeeded" in capsys.readouterr().out
