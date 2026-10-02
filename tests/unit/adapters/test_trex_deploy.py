from collections.abc import Sequence
from typing import Any

import pytest

from src.adapters.firefly import AlreadySubmitted, DeployResult, FireflyError
from src.adapters.trex_artifacts import LoadedArtifact
from src.adapters.trex_deploy import DeployStepError, run_plan
from src.core.firefly.operations import Operation
from src.core.trex.plan import Account, Artifact, Call, Deploy, Ref, Step

ADMIN = "0x" + "aa" * 20
ACCOUNTS = {"admin": ADMIN}
ABI = [
    {"type": "constructor", "inputs": [{"name": "owner", "type": "address"}]},
    {"type": "function", "name": "setThing", "inputs": [{"name": "thing", "type": "address"}]},
]


def load(artifact: Artifact) -> LoadedArtifact:
    return LoadedArtifact(artifact.path, ABI, "0x6080", 100, 110)


PLAN: list[Step] = [
    Deploy("first", Artifact("t-rex", "first"), (Account("admin"),)),
    Deploy("second", Artifact("t-rex", "second"), (Ref("first"),)),
    Call("second", "setThing", (Ref("first"),)),
]


class FakeClient:
    def __init__(
        self,
        fail_on: str | None = None,
        already: set[str] | None = None,
        original_status: str = "Succeeded",
        original_address: str | None = None,
        transient_first: set[str] | None = None,
        pending_polls: int = 0,
    ) -> None:
        self.original_status = original_status
        self.original_address = original_address
        self.transient_first = transient_first or set()
        self.pending_polls = pending_polls
        self.deploy_calls: list[str] = []
        self.deployed: list[tuple[str, list[Any], str | None, str | None]] = []
        self.invoked: list[tuple[str, str, dict[str, Any], str | None, str | None]] = []
        self.fail_on = fail_on
        self.already = already or set()
        self.generated: list[Any] = []

    def deploy(self, bytecode: str, abi: Any, constructor_input: Sequence[Any],
               key: str | None = None, idempotency_key: str | None = None,
               timeout: float = 0) -> DeployResult:
        name = (idempotency_key or "").removeprefix("trex-")
        self.deploy_calls.append(name)
        if name in self.transient_first and self.deploy_calls.count(name) == 1:
            raise FireflyError(
                'HTTP 500: FF10111: Error from ethereum connector: : Post "http://x/": '
                "context deadline exceeded (Client.Timeout exceeded while awaiting headers)"
            )
        if name in self.transient_first:  # the first attempt was in fact accepted
            raise AlreadySubmitted("tx-old-1234")
        if name == self.fail_on:
            raise FireflyError("HTTP 500: boom")
        if name in self.already:
            raise AlreadySubmitted("tx-old-1234")
        self.deployed.append((name, list(constructor_input), key, idempotency_key))
        address = "0x" + f"{len(self.deployed):02x}" * 20
        return DeployResult(address, Operation("op", "Succeeded"))

    def transaction_operations(self, transaction_id: str) -> list[Operation]:
        assert transaction_id == "tx-old-1234"
        if self.pending_polls > 0:
            self.pending_polls -= 1
            return [Operation("op-old", "Pending")]
        output = (
            {"contractLocation": {"address": self.original_address}}
            if self.original_address
            else {}
        )
        return [Operation("op-old", self.original_status, error="reverted", output=output)]

    def generate_interface(self, abi: Any) -> dict[str, Any]:
        self.generated.append(abi)
        return {"methods": [{"name": "setThing", "params": [{"name": "thing"}], "returns": []}]}

    def invoke(self, address: str, method: Any, inputs: Any, key: str | None = None,
               idempotency_key: str | None = None, timeout: float = 0) -> Operation:
        if idempotency_key in {f"trex-{n}" for n in self.already}:
            raise AlreadySubmitted("tx-old-1234")
        self.invoked.append((address, method["name"], dict(inputs), key, idempotency_key))
        return Operation("op", "Succeeded")


def code_everywhere(_address: str) -> str:
    return "0x6080"


def run(client: FakeClient, existing: dict[str, str] | None = None,
        code_at: Any = code_everywhere) -> tuple[dict[str, str], list[dict[str, str]]]:
    saved: list[dict[str, str]] = []
    result = run_plan(PLAN, client=client, load=load, accounts=ACCOUNTS, code_at=code_at,
                      existing=existing or {}, save=lambda m: saved.append(dict(m)),
                      log=lambda _line: None, sleep=lambda _s: None,
                      clock=iter(range(100_000)).__next__)
    return result, saved


def test_contracts_are_deployed_in_order_through_firefly_as_admin() -> None:
    client = FakeClient()
    addresses, _saved = run(client)
    assert [d[0] for d in client.deployed] == ["first", "second"]
    assert (client.deployed[0][1], client.deployed[0][2]) == ([ADMIN], ADMIN)  # args, signer
    assert client.deployed[1][1] == [addresses["first"]]  # a reference became an address
    assert addresses == {"first": "0x" + "01" * 20, "second": "0x" + "02" * 20}


def test_the_addresses_are_saved_after_every_success() -> None:
    _result, saved = run(FakeClient())
    assert saved == [
        {"first": "0x" + "01" * 20},
        {"first": "0x" + "01" * 20, "second": "0x" + "02" * 20},
    ]


def test_a_call_is_made_with_inputs_named_after_the_abi_parameters_and_a_stable_key() -> None:
    client = FakeClient()
    addresses, _ = run(client)
    assert client.invoked == [
        (addresses["second"], "setThing", {"thing": addresses["first"]}, ADMIN,
         "trex-second-setThing")
    ]  # fmt: skip


def test_a_failed_deploy_stops_the_run_and_names_the_contract_and_the_error() -> None:
    client = FakeClient(fail_on="second")
    with pytest.raises(DeployStepError, match=r"second.*HTTP 500: boom") as raised:
        run(client)
    assert raised.value.step == "second"
    assert client.invoked == []  # nothing after the failure ran


def test_a_contract_without_code_on_chain_is_an_error() -> None:
    with pytest.raises(DeployStepError, match=r"first.*no code"):
        run(FakeClient(), code_at=lambda _a: "0x")


def test_contracts_that_exist_with_code_are_skipped() -> None:
    client = FakeClient()
    existing = {"first": "0x" + "ee" * 20}
    addresses, _ = run(client, existing=existing)
    assert [d[0] for d in client.deployed] == ["second"]
    assert addresses["first"] == existing["first"]


def test_an_existing_address_without_code_is_deployed_again() -> None:
    client = FakeClient()
    codes = {"0x" + "ee" * 20: "0x"}
    run(client, existing={"first": "0x" + "ee" * 20}, code_at=lambda a: codes.get(a, "0x6080"))
    assert [d[0] for d in client.deployed] == ["first", "second"]


def test_a_deploy_that_succeeded_earlier_is_recovered_from_its_operation_output() -> None:
    address = "0x" + "9a" * 20
    client = FakeClient(already={"first"}, original_status="Succeeded", original_address=address)
    addresses, _ = run(client)
    assert addresses["first"] == address
    assert [d[0] for d in client.deployed] == ["second"]  # first was not deployed again


def test_a_deploy_that_succeeded_earlier_without_an_address_tells_the_user_to_reset() -> None:
    with pytest.raises(DeployStepError, match=r"first.*no address.*reset"):
        run(FakeClient(already={"first"}, original_status="Succeeded"))


def test_an_earlier_transaction_that_is_still_pending_is_waited_for() -> None:
    address = "0x" + "9b" * 20
    client = FakeClient(
        already={"first"}, original_status="Succeeded", original_address=address, pending_polls=3
    )
    addresses, _ = run(client)
    assert addresses["first"] == address


def test_an_earlier_transaction_that_never_finishes_is_an_error_naming_the_contract() -> None:
    client = FakeClient(already={"first"}, pending_polls=10_000)
    with pytest.raises(DeployStepError, match=r"first.*still pending"):
        run(client)


def test_a_timeout_is_retried_with_the_same_key_and_the_accepted_transaction_is_used() -> None:
    address = "0x" + "9c" * 20
    client = FakeClient(
        transient_first={"first"}, original_status="Succeeded", original_address=address
    )
    addresses, _ = run(client)
    assert addresses["first"] == address
    assert client.deploy_calls[:2] == ["first", "first"]  # same key twice, not a new one


def test_a_failure_that_is_not_transient_is_not_retried() -> None:
    client = FakeClient(fail_on="first")
    with pytest.raises(DeployStepError, match="HTTP 500: boom"):
        run(client)
    assert client.deploy_calls == ["first"]


def test_a_deploy_whose_earlier_attempt_failed_is_retried_with_a_new_key() -> None:
    client = FakeClient(already={"first"}, original_status="Failed")
    # The fake rejects only the plain key, so the retry (new key) goes through.
    addresses, _ = run(client)
    assert "first" in addresses
    assert client.deployed[0][3] == "trex-first-after-tx-old-1"


def test_a_call_whose_earlier_attempt_succeeded_counts_as_done() -> None:
    client = FakeClient(already={"second-setThing"}, original_status="Succeeded")
    run(client)
    assert client.invoked == []


def test_a_call_whose_earlier_attempt_failed_is_retried_with_a_new_key() -> None:
    client = FakeClient(already={"second-setThing"}, original_status="Failed")
    run(client)
    assert [call[4] for call in client.invoked] == ["trex-second-setThing-after-tx-old-1"]
