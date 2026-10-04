"""`python scripts/stack.py perf-setup`: N verified wallets holding COIN, for the benchmark.

The wallets are the ones Caliper derives per worker (`src/core/perf/wallets.py`). Each becomes a
T-REX investor exactly like Anson and Beatrice (identity, registry entry, KYC claim) and is then
minted COIN. Every step reads the state first, so a second run sends nothing.
"""

import json
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from src.adapters.addresses import DEPLOYED_ADDRESSES, read_addresses
from src.adapters.firefly import FireflyClient, http_transport
from src.adapters.perf_wallets import load_perf_wallets
from src.adapters.trex_apis import API_COIN
from src.adapters.trex_artifacts import load_artifact
from src.adapters.trex_deploy import submit
from src.adapters.trex_onboard import issue_claims, register_identities
from src.core.firefly.operations import Operation
from src.core.network.wallets import Wallet, account_addresses, wallet_private_key
from src.core.perf.setup import coins_missing
from src.core.perf.wallets import derive_wallets


class SetupClient(Protocol):
    """What the minting step needs from FireFly (the whole client also satisfies the others)."""

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any: ...

    def api_invoke(
        self,
        api: str,
        method: str,
        inputs: Mapping[str, Any],
        key: str | None = None,
        idempotency_key: str | None = None,
        timeout: float = ...,
    ) -> Operation: ...

    def transaction_operations(self, transaction_id: str) -> list[Operation]: ...


def mint_to_wallets(
    client: SetupClient,
    accounts: Mapping[str, str],
    names: Sequence[str],
    coins: int,
    log: Callable[[str], None],
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Top each named wallet up to `coins` COIN, minting as Admin. Wallets that have it are skipped.

    The idempotency key holds the balance the mint starts from, so a later top-up of the same
    wallet never reuses the key of an earlier mint (FireFly would answer that with the old one).
    """
    admin = accounts["admin"]
    for name in names:
        wallet = accounts[name]
        balance = int(client.api_query(API_COIN, "balanceOf", {"_userAddress": wallet}))
        missing = coins_missing(balance, coins)
        if missing == 0:
            continue
        inputs = {"_to": wallet, "_amount": str(missing)}

        def mint(key: str, inputs: dict[str, str] = inputs) -> Operation:
            return client.api_invoke(API_COIN, "mint", inputs, key=admin, idempotency_key=key)

        key = f"perf-mint-{name}-{balance}-{coins}"
        submit(f"coin.mint {name}", mint, key, client, sleep, clock)
        log(f"{name}  minted up to {coins} COIN")


def perf_setup(
    network_dir: Path,
    count: int,
    coins: int,
    addresses_file: Path = DEPLOYED_ADDRESSES,
    log: Callable[[str], None] = print,
    client: Any = None,
    load_wallets: Callable[[Sequence[Wallet]], list[str]] = load_perf_wallets,
    register: Callable[..., None] = register_identities,
    claim: Callable[..., None] = issue_claims,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    """Make `count` benchmark wallets verified investors with `coins` COIN each.

    Needs `deploy`. Returns the seconds it took (setup can take longer than the rounds, R7).
    """
    document = json.loads((network_dir / "wallets.json").read_text(encoding="utf-8"))
    addresses = read_addresses(addresses_file)
    if "id-factory" not in addresses:
        raise ValueError("nothing is deployed yet: run `python scripts/stack.py deploy` first")
    started = clock()
    wallets = derive_wallets(count)
    accounts = {**account_addresses(document), **{w.name: w.address for w in wallets}}
    names = [w.name for w in wallets]
    firefly = client or FireflyClient(http_transport())
    written = load_wallets(wallets)
    log(f"signer  {len(wallets)} benchmark wallets ({len(written)} new)")
    register(
        firefly, load_artifact, addresses, accounts, log, sleep=sleep, clock=clock, names=names
    )
    issuer_key = wallet_private_key(document, "admin")
    claim(
        firefly, load_artifact, addresses, accounts, issuer_key, log,
        sleep=sleep, clock=clock, names=names,
    )  # fmt: skip
    mint_to_wallets(firefly, accounts, names, coins, log, sleep, clock)
    seconds = clock() - started
    log(f"perf-setup  {count} wallets with {coins} COIN each in {seconds:.1f} s")
    return seconds
