"""Run the T-REX plan through FireFly: deploy contracts and make the wiring calls (adapter)."""

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from src.adapters.firefly import AlreadySubmitted, DeployResult, FireflyError
from src.adapters.trex_artifacts import LoadedArtifact
from src.core.firefly.operations import Operation, find_method, is_transient
from src.core.trex.plan import Artifact, Call, Deploy, Step, validate_plan
from src.core.trex.resolve import call_input, resolve_args


class DeployStepError(Exception):
    """A step of the plan failed. `step` names the contract (or `contract.method`)."""

    def __init__(self, step: str, reason: str) -> None:
        super().__init__(f"{step}: {reason}")
        self.step = step


class TransactionLog(Protocol):
    def transaction_operations(self, transaction_id: str) -> list[Operation]: ...


class Firefly(Protocol):
    def deploy(
        self,
        bytecode: str,
        abi: Sequence[Any],
        constructor_input: Sequence[Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = ...,
    ) -> DeployResult: ...

    def generate_interface(self, abi: Sequence[Any]) -> dict[str, Any]: ...

    def transaction_operations(self, transaction_id: str) -> list[Operation]: ...

    def invoke(
        self,
        address: str,
        method: Mapping[str, Any],
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = ...,
    ) -> Operation: ...


T = TypeVar("T")

PENDING_TIMEOUT = 180.0  # seconds to wait for an earlier transaction that is not final yet
TRANSIENT_RETRIES = 3
FAILED_RETRIES = 3


@dataclass(frozen=True)
class Earlier:
    """The write was already accepted before: these are its operations, all final."""

    operations: list[Operation]


def run_plan(
    plan: list[Step],
    *,
    client: Firefly,
    load: Callable[[Artifact], LoadedArtifact],
    accounts: Mapping[str, str],
    code_at: Callable[[str], str],
    existing: Mapping[str, str],
    save: Callable[[dict[str, str]], None],
    log: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, str]:
    """Run every step in order and return the address of each deployed contract.

    A contract that is already in `existing` and still has code on chain is skipped. Addresses are
    saved after each deploy. The first failure stops the run with a `DeployStepError`.
    """
    validate_plan(plan)
    addresses: dict[str, str] = {}
    artifacts: dict[str, LoadedArtifact] = {}
    for step in plan:
        if isinstance(step, Deploy):
            artifacts[step.name] = load(step.artifact)
            known = existing.get(step.name)
            if known and code_at(known) not in ("", "0x"):
                addresses[step.name] = known
                log(f"{step.name}  {known}  (already deployed)")
                continue
            addresses[step.name] = _deploy(
                step, artifacts[step.name], addresses, accounts, client, code_at, sleep, clock
            )
            save(addresses)
            log(f"{step.name}  {addresses[step.name]}")
        else:
            _call(step, artifacts[step.contract], addresses, accounts, client, log, sleep, clock)
    return addresses


def submit(
    name: str,
    send: Callable[[str], T],
    base_key: str,
    client: TransactionLog,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
) -> T | Earlier:
    """Send a write under a stable idempotency key and cope with what FireFly really does.

    - A timeout or dropped connection is retried with the same key (the first request may have
      been accepted anyway; then the retry gets `AlreadySubmitted`).
    - `AlreadySubmitted`: wait until the earlier transaction is final. If it failed, retry under
      a new key (FireFly keeps the key of a failed transaction); if it succeeded, use it.
    """
    key = base_key
    transient = failed = 0
    while True:
        try:
            return send(key)
        except AlreadySubmitted as earlier:
            operations = _wait_final(name, client, earlier.transaction_id, sleep, clock)
            if not all(operation.failed for operation in operations):
                return Earlier(operations)
            failed += 1
            if failed > FAILED_RETRIES:
                raise DeployStepError(
                    name, "failed again and again: " + str(operations[0].error)
                ) from earlier
            key = _retry_key(base_key, earlier.transaction_id)
        except FireflyError as error:
            transient += 1
            if not is_transient(str(error)) or transient > TRANSIENT_RETRIES:
                raise DeployStepError(name, str(error)) from error
            sleep(2.0 * transient)


def _wait_final(
    name: str,
    client: TransactionLog,
    transaction_id: str,
    sleep: Callable[[float], None],
    clock: Callable[[], float],
) -> list[Operation]:
    """The operations of a transaction once all of them are final (succeeded or failed)."""
    deadline = clock() + PENDING_TIMEOUT
    while True:
        try:
            operations = client.transaction_operations(transaction_id)
        except FireflyError as error:
            raise DeployStepError(name, str(error)) from error
        if operations and all(op.succeeded or op.failed for op in operations):
            return operations
        if clock() >= deadline:
            raise DeployStepError(
                name,
                f"transaction {transaction_id} is still pending after {PENDING_TIMEOUT:g}s",
            )
        sleep(2.0)


def _deploy(
    step: Deploy,
    artifact: LoadedArtifact,
    addresses: Mapping[str, str],
    accounts: Mapping[str, str],
    client: Firefly,
    code_at: Callable[[str], str],
    sleep: Callable[[float], None],
    clock: Callable[[], float],
) -> str:
    args = resolve_args(step.args, addresses, accounts)

    def send(key: str) -> DeployResult:
        return client.deploy(
            artifact.bytecode, artifact.abi, args, key=accounts["admin"], idempotency_key=key
        )

    outcome = submit(step.name, send, f"trex-{step.name}", client, sleep, clock)
    address = (
        _address_from(outcome.operations) if isinstance(outcome, Earlier) else outcome.address
    )
    if address is None:
        raise DeployStepError(
            step.name,
            "an earlier attempt succeeded but its operation has no address. "
            "Run `python scripts/stack.py reset` to start from a clean chain.",
        )
    if code_at(address) in ("", "0x"):
        raise DeployStepError(step.name, f"FireFly reported {address} but it has no code")
    return address


def _address_from(operations: list[Operation]) -> str | None:
    for operation in operations:
        location = operation.output.get("contractLocation")
        if operation.succeeded and isinstance(location, Mapping) and location.get("address"):
            return str(location["address"]).lower()
    return None


def _call(
    step: Call,
    artifact: LoadedArtifact,
    addresses: Mapping[str, str],
    accounts: Mapping[str, str],
    client: Firefly,
    log: Callable[[str], None],
    sleep: Callable[[float], None],
    clock: Callable[[], float],
) -> None:
    name = f"{step.contract}.{step.method}"
    try:
        abi_method = next(
            e for e in artifact.abi if e.get("type") == "function" and e.get("name") == step.method
        )
        method = find_method(client.generate_interface(artifact.abi), step.method)
        inputs = call_input(abi_method["inputs"], resolve_args(step.args, addresses, accounts))
    except (FireflyError, ValueError, StopIteration) as error:
        raise DeployStepError(name, str(error) or type(error).__name__) from error

    def send(key: str) -> Operation:
        return client.invoke(
            addresses[step.contract], method, inputs, key=accounts[step.sender], idempotency_key=key
        )

    outcome = submit(name, send, f"trex-{step.contract}-{step.method}", client, sleep, clock)
    log(f"{name}  (already done)" if isinstance(outcome, Earlier) else name)


def _retry_key(base_key: str, transaction_id: str) -> str:
    """FireFly keeps an idempotency key even after the transaction failed, so retry under a new
    one that is the same every time for the same failed transaction."""
    return f"{base_key}-after-{transaction_id[:8]}"
