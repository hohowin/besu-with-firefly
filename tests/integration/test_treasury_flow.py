"""Branch funding on the live stack: LDN asks in CAD, TOR approves, the treasury converts, LDN
redeems. The app under test runs in this process; reads and the negative calls go straight to
FireFly with the test helper, so a bug in the app cannot hide a bug in the contracts."""

import json
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from src.adapters.docker_stack import REPO_ROOT
from src.adapters.treasury_app import LONDON, Sweeper, build_app
from src.core.treasury.dates import processing_date
from src.core.treasury.ids import request_id_from_uuid
from tests.support.deploy import run_stack
from tests.support.firefly import ff_post

pytestmark = pytest.mark.integration

NS = "/api/v1/namespaces/default"
WAIT = 120.0


def wallets() -> dict[str, str]:
    document = json.loads((REPO_ROOT / "network-config" / "wallets.json").read_text("utf-8"))
    return {w["name"]: w["address"] for w in document["wallets"]}


# ---- independent reads and writes, straight to FireFly ----


def query(api: str, method: str, inputs: dict[str, Any] | None = None) -> Any:
    body = {"input": inputs} if inputs else {}
    return ff_post(f"{NS}/apis/{api}/query/{method}", body)["output"]


def chain_request(request_uuid: str) -> dict[str, Any]:
    return dict(query("funding-request", "getRequest", {"id": request_id_from_uuid(request_uuid)}))


def all_requests() -> list[dict[str, Any]]:
    count = int(query("funding-request", "requestCount"))
    ids = [query("funding-request", "requestIdAt", {"index": str(i)}) for i in range(count)]
    return [dict(query("funding-request", "getRequest", {"id": rid})) for rid in ids]


def direct(method: str, inputs: dict[str, str], signer: str) -> tuple[bool, str]:
    """A write straight to the contract API. Returns (accepted, text of the answer)."""
    request = urllib.request.Request(
        f"http://localhost:5000{NS}/apis/funding-request/invoke/{method}?confirm=true",
        data=json.dumps({"input": inputs, "key": wallets()[signer]}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            return True, response.read().decode()
    except urllib.error.HTTPError as error:
        return False, error.read().decode()


def supplies() -> tuple[int, int]:
    return int(query("cadc", "totalSupply")), int(query("gbpc", "totalSupply"))


def assert_conserved() -> None:
    """I1 and I2 on the chain: CADC outstanding = CAD of Approved, GBPC = GBP of Settled. Retries
    briefly because a background settlement can land between the reads."""
    deadline = time.monotonic() + 30
    while True:
        requests = all_requests()
        cadc, gbpc = supplies()
        want_cad = sum(int(r["amountCad"]) for r in requests if r["status"] == "2")
        want_gbp = sum(int(r["amountGbp"]) for r in requests if r["status"] == "4")
        if (cadc, gbpc) == (want_cad, want_gbp):
            return
        assert time.monotonic() < deadline, (
            f"supplies {cadc}/{gbpc}, requests say {want_cad}/{want_gbp}"
        )
        time.sleep(1)


def wait_status(request_uuid: str, status: int, timeout: float = WAIT) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        found = chain_request(request_uuid)
        if int(found["status"]) == status:
            return found
        assert time.monotonic() < deadline, f"still status {found['status']}, wanted {status}"
        time.sleep(1)


# ---- the app under test ----


@dataclass
class App:
    base: str
    fx_file: Path
    sweeper: Sweeper

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Content-Type": "application/json"},
        )  # fmt: skip
        try:
            with urllib.request.urlopen(request, timeout=180) as response:  # noqa: S310
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def create(self, amount: str, request_uuid: str | None = None) -> tuple[str, int, Any]:
        request_uuid = request_uuid or str(uuid.uuid4())
        status, body = self.call(
            "POST", "/api/requests", {"as": "ldn", "amount": amount, "id": request_uuid}
        )
        return request_uuid, status, body

    def set_rates(self, document: dict[str, Any]) -> None:
        self.fx_file.write_text(json.dumps(document), encoding="utf-8")


RATES = {"CADGBP": {"default": "0.580000"}}


@pytest.fixture(scope="module")
def app(
    stack: object, deployed: dict[str, str], tmp_path_factory: pytest.TempPathFactory
) -> Iterator[App]:
    result = run_stack("treasury")
    assert result.returncode == 0, f"treasury failed:\n{result.stdout}\n{result.stderr}"
    fx_file = tmp_path_factory.mktemp("fx") / "fx-rates.json"
    fx_file.write_text(json.dumps(RATES), encoding="utf-8")
    server, sweeper = build_app(port=0, fx_file=fx_file, log=lambda _entry: None)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield App(f"http://127.0.0.1:{server.server_address[1]}", fx_file, sweeper)
    server.shutdown()
    server.server_close()


@pytest.fixture(autouse=True)
def default_rates(request: pytest.FixtureRequest) -> None:
    if "app" in request.fixturenames:
        request.getfixturevalue("app").set_rates(RATES)


# ---- tests ----


def admin_nonce() -> int:
    payload = {"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionCount",
               "params": [wallets()["admin"], "latest"]}  # fmt: skip
    request = urllib.request.Request(
        "http://localhost:8545",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as answer:  # noqa: S310
        return int(json.loads(answer.read())["result"], 16)


def test_treasury_deploy_is_idempotent(app: App) -> None:
    before = admin_nonce()
    again = run_stack("treasury")
    assert again.returncode == 0, again.stderr
    assert admin_nonce() == before  # a second run sent nothing
    assert query("funding-request", "treasury").lower() == wallets()["treasury"].lower()
    assert query("cadc", "controller") == query("gbpc", "controller")


def test_funding_happy_path(app: App) -> None:
    started = time.monotonic()
    cadc0, gbpc0 = supplies()
    request_uuid, status, body = app.create("1000.00")
    assert (status, body["status"]) == (202, "done")

    created = chain_request(request_uuid)
    assert (created["status"], created["amountCad"]) == ("1", "100000")
    assert created["processingDate"] == str(processing_date(datetime.now(UTC), LONDON))
    assert supplies() == (cadc0, gbpc0)  # nothing minted yet

    status, body = app.call("POST", f"/api/requests/{request_uuid}/approve", {"as": "tor"})
    assert (status, body["status"]) == (202, "done")
    # steps 5 to 7 follow on their own
    final = wait_status(request_uuid, 5)
    assert (final["amountGbp"], final["ratePpm"]) == ("58000", "580000")
    assert supplies() == (cadc0, gbpc0)  # CADC burned, GBPC minted and burned again
    assert time.monotonic() - started < 60 + 60  # the PRD budget is 60 s; allow a slow machine
    assert_conserved()

    status, view = app.call("GET", f"/api/requests/{request_uuid}")
    assert (view["status"], view["amountGbp"], view["rate"]) == ("redeemed", "580.00", "0.580000")
    # the service writes its own steps just after the chain shows them, so allow a moment
    deadline = time.monotonic() + 15
    while True:
        _, view = app.call("GET", f"/api/requests/{request_uuid}")
        actions = [step["action"] for step in view["steps"]]
        if actions == ["create", "approve", "settle", "redeem"] or time.monotonic() > deadline:
            break
        time.sleep(1)
    assert actions == ["create", "approve", "settle", "redeem"]


def test_reject_mints_nothing(app: App) -> None:
    before = supplies()
    request_uuid, status, _ = app.create("25.00")
    assert status == 202
    status, body = app.call(
        "POST", f"/api/requests/{request_uuid}/reject", {"as": "tor", "reason": "over budget"}
    )
    assert (status, body["status"]) == (202, "done")
    assert chain_request(request_uuid)["status"] == "3"
    assert supplies() == before
    assert_conserved()


def test_the_requester_cannot_approve_their_own_request(app: App) -> None:
    """`ldn` holds no approver role here, so the contract answers NotApprover (SelfApproval is
    for a wallet that is both, and is covered by the contract tests)."""
    request_uuid, _, _ = app.create("10.00")
    status, body = app.call("POST", f"/api/requests/{request_uuid}/approve", {"as": "ldn"})
    assert (status, body["error"]) == (403, "NotApprover")
    ok, text = direct("approve", {"id": request_id_from_uuid(request_uuid)}, "ldn")
    assert not ok and "EVM reverted" in text
    assert chain_request(request_uuid)["status"] == "1"


def test_a_wallet_without_the_approver_role_is_refused(app: App) -> None:
    request_uuid, _, _ = app.create("10.00")
    status, body = app.call("POST", f"/api/requests/{request_uuid}/approve", {"as": "treasury"})
    assert (status, body["error"]) == (403, "NotApprover")
    assert chain_request(request_uuid)["status"] == "1"


def test_approving_twice_mints_once(app: App) -> None:
    app.set_rates({"CADGBP": {"2000-01-01": "0.5"}})  # no rate for today: it stays Approved
    cadc0, _ = supplies()
    request_uuid, _, _ = app.create("40.00")
    status, _ = app.call("POST", f"/api/requests/{request_uuid}/approve", {"as": "tor"})
    assert status == 202
    # the same click again is the same write (same idempotency key): pending, never done twice
    status, body = app.call("POST", f"/api/requests/{request_uuid}/approve", {"as": "tor"})
    assert (status, body["status"]) == (202, "pending")
    # a different write (no key) is refused by the contract itself
    ok, text = direct("approve", {"id": request_id_from_uuid(request_uuid)}, "tor")
    assert not ok and "EVM reverted" in text
    assert supplies()[0] == cadc0 + 4000
    assert chain_request(request_uuid)["status"] == "2"
    app.set_rates(RATES)
    app.call("POST", f"/api/requests/{request_uuid}/retry-settle", {})
    wait_status(request_uuid, 5)
    assert_conserved()


def test_a_missing_fx_rate_blocks_settlement_until_it_is_added(app: App) -> None:
    app.set_rates({"CADGBP": {"2000-01-01": "0.5"}})  # no rate for today and no default
    request_uuid, _, _ = app.create("50.00")
    app.call("POST", f"/api/requests/{request_uuid}/approve", {"as": "tor"})
    time.sleep(8)  # the background sweep has had its chance
    assert chain_request(request_uuid)["status"] == "2"  # still Approved
    status, view = app.call("GET", f"/api/requests/{request_uuid}")
    assert "no CADGBP rate" in (view["note"] or "")
    assert int(query("cadc", "balanceOf", {"account": wallets()["treasury"]})) >= 5000

    ok, text = direct(
        "settle", {"id": request_id_from_uuid(request_uuid), "ratePpm": "580000"}, "tor"
    )
    assert not ok and "EVM reverted" in text  # only the treasury wallet may settle
    ok, text = direct("redeem", {"id": request_id_from_uuid(request_uuid)}, "ldn")
    assert not ok  # nothing to redeem before settlement

    app.set_rates(RATES)
    status, _ = app.call("POST", f"/api/requests/{request_uuid}/retry-settle", {})
    assert status == 202
    final = wait_status(request_uuid, 5)
    assert final["amountGbp"] == "2900"
    assert_conserved()


def test_only_the_beneficiary_can_redeem(app: App) -> None:
    """Approve and settle by hand (no app step), so the request waits in Settled."""
    request_uuid, _, _ = app.create("20.00")
    rid = request_id_from_uuid(request_uuid)
    assert direct("approve", {"id": rid}, "tor")[0]
    assert direct("settle", {"id": rid, "ratePpm": "580000"}, "treasury")[0]
    assert chain_request(request_uuid)["status"] == "4"
    ok, text = direct("redeem", {"id": rid}, "tor")
    assert not ok and "EVM reverted" in text
    assert chain_request(request_uuid)["status"] == "4"
    assert direct("redeem", {"id": rid}, "ldn")[0]
    assert chain_request(request_uuid)["status"] == "5"
    assert_conserved()


def test_a_repeated_create_is_one_request(app: App) -> None:
    count = int(query("funding-request", "requestCount"))
    request_uuid, first, _ = app.create("7.00")
    _, second, body = app.create("7.00", request_uuid)
    assert first == 202
    assert (second, body["status"]) == (202, "pending")  # same idempotency key: never "done" twice
    assert int(query("funding-request", "requestCount")) == count + 1


def test_restart_recovery_finishes_what_was_left_approved(app: App) -> None:
    request_uuid, _, _ = app.create("30.00")
    rid = request_id_from_uuid(request_uuid)
    assert direct("approve", {"id": rid}, "tor")[0]  # approved with no app involved
    assert int(chain_request(request_uuid)["status"]) == 2
    app.sweeper.trigger()  # what the app does when it starts
    final = wait_status(request_uuid, 5)
    assert final["amountGbp"] == "1740"
    assert_conserved()


@pytest.mark.parametrize("amount", ["0", "-5", "1000.001", "abc", "1e3", "9999999.00"])
def test_a_bad_amount_is_refused_before_anything_is_sent(app: App, amount: str) -> None:
    count = int(query("funding-request", "requestCount"))
    _, status, body = app.create(amount)
    assert (status, body["error"]) == (400, "invalid_amount")
    assert int(query("funding-request", "requestCount")) == count


def test_the_ledger_matches_the_chain(app: App) -> None:
    assert_conserved()
    status, books = app.call("GET", "/api/balances")
    assert status == 200 and books["conserved"] is True
    cadc, gbpc = supplies()
    assert books["supply"]["cadc"] == f"{cadc // 100}.{cadc % 100:02d}"
    assert books["supply"]["gbpc"] == f"{gbpc // 100}.{gbpc % 100:02d}"
    status, listing = app.call("GET", "/api/requests")
    assert len(listing["requests"]) == len(all_requests())


def test_the_tokens_cannot_be_moved_by_a_holder(app: App) -> None:
    """The tokens have no transfer, approve or transferFrom: the FireFly API does not offer them."""
    for api, method, inputs in (
        ("cadc", "transfer", {"to": wallets()["ldn"], "amount": "1"}),
        ("gbpc", "approve", {"spender": wallets()["ldn"], "amount": "1"}),
        ("gbpc", "transferFrom", {"from": wallets()["ldn"], "to": wallets()["tor"], "amount": "1"}),
    ):
        request = urllib.request.Request(
            f"http://localhost:5000{NS}/apis/{api}/invoke/{method}?confirm=true",
            data=json.dumps({"input": inputs, "key": wallets()["ldn"]}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as refused:
            urllib.request.urlopen(request, timeout=30)  # noqa: S310
        assert refused.value.code in (400, 404)
        refused.value.close()


def test_a_rate_outside_the_contract_bounds_is_refused_and_explained(app: App) -> None:
    app.set_rates({"CADGBP": {"default": "0.900000"}})  # a typo for 0.58: outside 0.40 to 0.80
    request_uuid, _, _ = app.create("60.00")
    app.call("POST", f"/api/requests/{request_uuid}/approve", {"as": "tor"})
    time.sleep(10)  # the background sweep has tried and been refused
    assert chain_request(request_uuid)["status"] == "2"  # still Approved, nothing converted
    _, view = app.call("GET", f"/api/requests/{request_uuid}")
    assert "outside the range" in (view["note"] or "")
    ok, text = direct(
        "settle", {"id": request_id_from_uuid(request_uuid), "ratePpm": "900000"}, "treasury"
    )
    assert not ok and "BadRate" in text  # the contract itself says no

    app.set_rates(RATES)  # the rate is corrected, then it goes through
    status, _ = app.call("POST", f"/api/requests/{request_uuid}/retry-settle", {})
    assert status == 202
    assert wait_status(request_uuid, 5)["amountGbp"] == "3480"
    assert_conserved()
