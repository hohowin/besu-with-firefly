"""`python scripts/stack.py treasury`: wallets, contracts, FireFly APIs, a wiring check (adapter).

Reuses the T-REX plan runner, so a re-run sends nothing that is already done.
"""

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

from eth_account import Account

from src.adapters.addresses import DEPLOYED_ADDRESSES, read_addresses, update_addresses
from src.adapters.firefly import FireflyClient, http_transport
from src.adapters.perf_wallets import load_perf_wallets
from src.adapters.rpc import get_code, wait_for_chain
from src.adapters.treasury_artifacts import load_treasury_artifact
from src.adapters.trex_deploy import DeployStepError, run_plan
from src.core.network.wallets import Wallet, account_addresses, build_wallets_document
from src.core.treasury.plan import APIS, NEW_WALLETS, TREASURY_ACCOUNTS, build_plan
from src.core.trex.plan import Artifact

INTERFACE_VERSION = "1.0.0"


class Registrar(Protocol):
    def ensure_interface(self, name: str, version: str, abi: Sequence[Any]) -> str: ...

    def ensure_api(self, name: str, interface_id: str, address: str) -> str: ...

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any: ...


def new_wallet(name: str) -> Wallet:
    account = Account.create()
    return Wallet(name, str(account.address).lower(), "0x" + account.key.hex())


def ensure_wallets(
    network_dir: Path,
    names: Sequence[str] = NEW_WALLETS,
    load: Callable[[Sequence[Wallet]], list[str]] = load_perf_wallets,
    create: Callable[[str], Wallet] = new_wallet,
) -> dict[str, str]:
    """Add the wallets that `wallets.json` lacks, give the signer their keystores, and return
    every wallet name with its address. A wallet that exists is never replaced."""
    path = network_dir / "wallets.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    known = [Wallet(w["name"], w["address"], w["privateKey"]) for w in document["wallets"]]
    have = {w.name for w in known}
    added = [create(name) for name in names if name not in have]
    if added:
        document = build_wallets_document(known + added)
        path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8", newline="\n")
    load([w for w in known + added if w.name in names])
    return account_addresses(document)


def register_treasury_apis(
    client: Registrar,
    load: Callable[[Artifact], Any],
    addresses: Mapping[str, str],
    log: Callable[[str], None],
) -> None:
    """An interface and a contract API per contract. Safe to repeat."""
    for api, contract, artifact in APIS:
        interface_id = client.ensure_interface(api, INTERFACE_VERSION, load(artifact).abi)
        client.ensure_api(api, interface_id, addresses[contract])
        log(f"api {api}  {addresses[contract]}")


def check_wiring(
    client: Registrar, addresses: Mapping[str, str], accounts: Mapping[str, str]
) -> None:
    """Read back what the constructor and `setController` should have set."""
    expected = [
        ("cadc", "controller", addresses["funding-request"]),
        ("gbpc", "controller", addresses["funding-request"]),
        ("funding-request", "treasury", accounts["treasury"]),
        ("funding-request", "cadc", addresses["cadc"]),
        ("funding-request", "gbpc", addresses["gbpc"]),
    ]
    for api, method, want in expected:
        found = str(client.api_query(api, method, {})).lower()
        if found != want.lower():
            raise DeployStepError(f"{api}.{method}", f"should be {want}, it is {found}")


def deploy_treasury(
    network_dir: Path,
    out: Path = DEPLOYED_ADDRESSES,
    log: Callable[[str], None] = print,
    wait: Callable[[], None] = wait_for_chain,
) -> dict[str, str]:
    """Create the wallets, deploy `cadc`, `gbpc` and `funding-request` through FireFly, register
    their APIs and check the wiring. Needs the stack up. Running it again sends nothing."""
    wait()
    accounts = ensure_wallets(network_dir)
    client = FireflyClient(http_transport())

    def save(found: dict[str, str]) -> None:
        update_addresses(out, found)

    deployed = run_plan(
        build_plan(),
        client=client,
        load=load_treasury_artifact,
        accounts=accounts,
        code_at=get_code,
        existing=read_addresses(out),
        save=save,
        log=log,
        known_accounts=TREASURY_ACCOUNTS,
    )
    save(deployed)
    register_treasury_apis(client, load_treasury_artifact, deployed, log)
    check_wiring(client, deployed, accounts)
    log("treasury  wired")
    return deployed
