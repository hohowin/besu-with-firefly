"""Run the T-REX plan through FireFly: deploy contracts and make the wiring calls (adapter)."""

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from src.adapters.firefly import (
    AlreadySubmitted,
    DeployResult,
    FireflyClient,
    FireflyError,
    http_transport,
)
from src.adapters.rpc import get_code
from src.adapters.trex_artifacts import REPO_ROOT, LoadedArtifact, load_artifact
from src.core.firefly.operations import Operation, find_method
from src.core.network.wallets import account_addresses
from src.core.trex.plan import Artifact, Call, Deploy, Step, build_plan, validate_plan
from src.core.trex.resolve import call_input, resolve_args

DEPLOYED_ADDRESSES = REPO_ROOT / "deployed-addresses.json"


class DeployStepError(Exception):
    """A step of the plan failed. `step` names the contract (or `contract.method`)."""

    def __init__(self, step: str, reason: str) -> None:
        super().__init__(f"{step}: {reason}")
        self.step = step


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
            addresses[step.name] = _deploy(step, artifacts[step.name], addresses, accounts, client,
                                           code_at)  # fmt: skip
            save(addresses)
            log(f"{step.name}  {addresses[step.name]}")
        else:
            _call(step, artifacts[step.contract], addresses, accounts, client, log)
    return addresses


def _deploy(
    step: Deploy,
    artifact: LoadedArtifact,
    addresses: Mapping[str, str],
    accounts: Mapping[str, str],
    client: Firefly,
    code_at: Callable[[str], str],
) -> str:
    args = resolve_args(step.args, addresses, accounts)
    base_key = f"trex-{step.name}"

    def attempt(key: str) -> DeployResult:
        return client.deploy(
            artifact.bytecode, artifact.abi, args, key=accounts["admin"], idempotency_key=key
        )

    try:
        try:
            result = attempt(base_key)
        except AlreadySubmitted as earlier:
            if not _earlier_attempt_failed(client, earlier.transaction_id):
                raise DeployStepError(
                    step.name,
                    f"already submitted as transaction {earlier.transaction_id}, but its address "
                    "is not recorded. Run `python scripts/stack.py reset` to start from a clean "
                    "chain.",
                ) from earlier
            result = attempt(_retry_key(base_key, earlier.transaction_id))
    except FireflyError as error:
        raise DeployStepError(step.name, str(error)) from error
    if code_at(result.address) in ("", "0x"):
        raise DeployStepError(step.name, f"FireFly reported {result.address} but it has no code")
    return result.address


def _call(
    step: Call,
    artifact: LoadedArtifact,
    addresses: Mapping[str, str],
    accounts: Mapping[str, str],
    client: Firefly,
    log: Callable[[str], None],
) -> None:
    name = f"{step.contract}.{step.method}"
    try:
        abi_method = next(
            e for e in artifact.abi if e.get("type") == "function" and e.get("name") == step.method
        )
        method = find_method(client.generate_interface(artifact.abi), step.method)
        inputs = call_input(abi_method["inputs"], resolve_args(step.args, addresses, accounts))
        base_key = f"trex-{step.contract}-{step.method}"

        def attempt(key: str) -> Operation:
            return client.invoke(
                addresses[step.contract], method, inputs, key=accounts[step.sender],
                idempotency_key=key,
            )  # fmt: skip

        try:
            attempt(base_key)
        except AlreadySubmitted as earlier:
            if not _earlier_attempt_failed(client, earlier.transaction_id):
                log(f"{name}  (already done)")
                return
            attempt(_retry_key(base_key, earlier.transaction_id))
    except (FireflyError, ValueError, StopIteration) as error:
        raise DeployStepError(name, str(error) or type(error).__name__) from error
    log(name)


def _earlier_attempt_failed(client: Firefly, transaction_id: str) -> bool:
    """True when every operation of the earlier transaction failed, so retrying is safe."""
    operations = client.transaction_operations(transaction_id)
    return bool(operations) and all(operation.failed for operation in operations)


def _retry_key(base_key: str, transaction_id: str) -> str:
    """FireFly keeps an idempotency key even after the transaction failed, so retry under a new
    one that is the same every time for the same failed transaction."""
    return f"{base_key}-after-{transaction_id[:8]}"


def deploy_trex(
    network_dir: Path,
    out: Path = DEPLOYED_ADDRESSES,
    log: Callable[[str], None] = print,
) -> dict[str, str]:
    """Deploy the T-REX infrastructure through the running FireFly. Writes `out` as it goes."""
    document = json.loads((network_dir / "wallets.json").read_text(encoding="utf-8"))
    existing: dict[str, str] = {}
    if out.is_file():
        existing = json.loads(out.read_text(encoding="utf-8"))

    def save(addresses: dict[str, str]) -> None:
        text = json.dumps(addresses, indent=2) + "\n"
        out.write_text(text, encoding="utf-8", newline="\n")

    return run_plan(
        build_plan(),
        client=FireflyClient(http_transport()),
        load=load_artifact,
        accounts=account_addresses(document),
        code_at=get_code,
        existing=existing,
        save=save,
        log=log,
    )
