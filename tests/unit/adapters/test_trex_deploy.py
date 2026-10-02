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
    ) -> None:
        self.original_status = original_status
        self.deployed: list[tuple[str, list[Any], str | None, str | None]] = []
        self.invoked: list[tuple[str, str, dict[str, Any], str | None, str | None]] = []
        self.fail_on = fail_on
        self.already = already or set()
        self.generated: list[Any] = []

    def deploy(self, bytecode: str, abi: Any, constructor_input: Sequence[Any],
               key: str | None = None, idempotency_key: str | None = None,
               timeout: float = 0) -> DeployResult:
        name = (idempotency_key or "").removeprefix("trex-")
        if name == self.fail_on:
            raise FireflyError("HTTP 500: boom")
        if name in self.already:
            raise AlreadySubmitted("tx-old-1234")
        self.deployed.append((name, list(constructor_input), key, idempotency_key))
        address = "0x" + f"{len(self.deployed):02x}" * 20
        return DeployResult(address, Operation("op", "Succeeded"))

    def transaction_operations(self, transaction_id: str) -> list[Operation]:
        assert transaction_id == "tx-old-1234"
        return [Operation("op-old", self.original_status, error="reverted")]

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
                      log=lambda _line: None)
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


def test_a_deploy_that_succeeded_earlier_but_is_not_recorded_tells_the_user_to_reset() -> None:
    with pytest.raises(DeployStepError, match=r"first.*already submitted.*reset"):
        run(FakeClient(already={"first"}, original_status="Succeeded"))


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
