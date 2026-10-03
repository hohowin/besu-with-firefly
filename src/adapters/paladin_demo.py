"""The Noto demo: mint, transfer, then show what each party and each node can see (adapter)."""

import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from src.adapters.addresses import DEPLOYED_ADDRESSES, read_addresses
from src.adapters.paladin import PALADIN_NODES, PaladinClient, http_transport
from src.adapters.paladin_artifacts import load_noto_private_abi
from src.adapters.paladin_noto import balance_of, coin_states, deploy_token, mint, transfer
from src.core.paladin.bootstrap import ADDRESS_NAMES
from src.core.paladin.noto import NOTARY, identity
from src.core.paladin.privacy import coin_amounts, visibility_problems

ANSON = identity("anson", "node2")
BEATRICE = identity("beatrice", "node3")
MINTED = 100
SENT = 40
NODES = ("node1", "node2", "node3")
ROLES = {"node1": "notary", "node2": "Anson", "node3": "Beatrice"}


class NotDeployed(Exception):
    """The Paladin contracts are not on the chain, so there is no Noto to use."""


class DemoFailed(Exception):
    """The demo ran but a node saw something it should not (or missed something)."""


class DemoClient(Protocol):
    def send_and_wait(self, node: str, transaction: Mapping[str, Any]) -> dict[str, Any]: ...

    def private_call(self, node: str, call: Mapping[str, Any]) -> Any: ...

    def call(self, node: str, method: str, params: list[Any] | None = None) -> Any: ...


def _seen(client: DemoClient, token: str) -> dict[str, list[int]]:
    return {node: coin_amounts(coin_states(client, node, token)) for node in NODES}


def run_noto_demo(
    client: DemoClient,
    abi: Sequence[Mapping[str, Any]],
    addresses: Mapping[str, str],
    log: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    settle_timeout: float = 30.0,
) -> str:
    """Deploy a new token, mint to Anson, send some to Beatrice and print the result.

    Returns the token address. Raises `NotDeployed` before sending anything if `deploy` has not
    run, and `DemoFailed` if a node's view of the coins differs from what Noto promises.
    """
    if not all(name in addresses for name in ADDRESS_NAMES.values()):
        raise NotDeployed("the Paladin contracts are not deployed, run `stack.py deploy` first")

    token = deploy_token(client)
    log(f"noto token {token}  notary {NOTARY}")
    mint(client, token, abi, ANSON, MINTED)
    log(f"minted {MINTED} to {ANSON} (submitted on node1)")
    transfer(client, token, abi, ANSON, BEATRICE, SENT)
    log(f"transferred {SENT} from {ANSON} to {BEATRICE} (submitted on node2)")

    expected = {
        "node1": [SENT, MINTED - SENT, MINTED],
        "node2": [SENT, MINTED - SENT, MINTED],
        "node3": [SENT],
    }
    deadline = clock() + settle_timeout
    while True:  # coins reach their owner's node a moment after the receipt
        seen = _seen(client, token)
        problems = visibility_problems(seen, expected)
        balances = {
            account: balance_of(client, token, abi, account) for account in (ANSON, BEATRICE)
        }
        if not problems and balances == {ANSON: MINTED - SENT, BEATRICE: SENT}:
            break
        if clock() >= deadline:
            raise DemoFailed(
                "; ".join(problems) or f"balances are {balances}, expected {MINTED - SENT}/{SENT}"
            )
        sleep(1.0)

    for account, balance in balances.items():
        log(f"balance {account:<15} {balance}")
    for node in NODES:
        log(f"{node} ({ROLES[node]}) sees coins {seen[node]}")
    log("privacy ok: the third node never saw Anson's 100 or his 60")
    return token


def noto_demo(addresses_file: Path = DEPLOYED_ADDRESSES, log: Callable[[str], None] = print) -> str:
    """The demo against the live stack."""
    return run_noto_demo(
        PaladinClient(PALADIN_NODES, http_transport()),
        abi=load_noto_private_abi(),
        addresses=read_addresses(addresses_file),
        log=log,
    )
