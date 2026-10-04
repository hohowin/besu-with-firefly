"""A write through a contract API, and what it did to the balances (pure orchestration).

For a `transfer` the sender's and recipient's balances are read before the write and after it, so
the caller can show the change, or confirm that a refused transfer moved nothing. The contract,
not this code, decides whether a transfer is allowed.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from src.core.firefly.errors import FireflyError
from src.core.firefly.outcome import Outcome, classify_error, classify_operation
from src.core.firefly.port import ContractApiPort

BALANCE_METHOD = "balanceOf"
BALANCE_ARGUMENT = "_userAddress"


@dataclass(frozen=True)
class InvokeReport:
    outcome: Outcome
    before: dict[str, str] = field(default_factory=dict)  # address to balance, base units
    after: dict[str, str] = field(default_factory=dict)


def run_invoke(
    port: ContractApiPort,
    api: str,
    method: str,
    inputs: Mapping[str, str],
    key: str,
    timeout: float = 120.0,
) -> InvokeReport:
    parties = _parties(method, inputs, key)
    before = _balances(port, api, parties)  # a failure here stops before anything is sent
    try:
        outcome = classify_operation(port.api_invoke(api, method, inputs, key=key, timeout=timeout))
    except FireflyError as error:
        outcome = classify_error(error)
    try:
        after = _balances(port, api, parties)
    except FireflyError:
        after = {}  # the write's outcome is already known; do not hide it behind a failed read
    return InvokeReport(outcome, before, after)


def _parties(method: str, inputs: Mapping[str, str], key: str) -> list[str]:
    recipient = inputs.get("_to")
    if method != "transfer" or recipient is None:
        return []
    return [key] if recipient == key else [key, recipient]


def _balances(port: ContractApiPort, api: str, addresses: list[str]) -> dict[str, str]:
    return {
        address: str(port.api_query(api, BALANCE_METHOD, {BALANCE_ARGUMENT: address}))
        for address in addresses
    }
