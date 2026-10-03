"""`python scripts/stack.py deploy`: deploy the T-REX suite, create COIN, register its APIs."""

import json
from collections.abc import Callable
from pathlib import Path

from src.adapters.addresses import DEPLOYED_ADDRESSES, read_addresses, update_addresses
from src.adapters.firefly import FireflyClient, http_transport
from src.adapters.rpc import get_code
from src.adapters.trex_apis import register_apis, unpause_token
from src.adapters.trex_artifacts import load_artifact
from src.adapters.trex_deploy import run_plan
from src.adapters.trex_onboard import issue_claims, mint_initial_supply, register_identities
from src.adapters.trex_suite import read_suite
from src.core.network.wallets import account_addresses, wallet_private_key
from src.core.trex.plan import build_plan


def deploy_trex(
    network_dir: Path,
    out: Path = DEPLOYED_ADDRESSES,
    log: Callable[[str], None] = print,
) -> dict[str, str]:
    """Deploy the T-REX infrastructure through the running FireFly and create `COIN`.

    Then registers the contract APIs `coin` and `identity-registry`, unpauses the token and
    registers and verifies the demo investors and mints the initial supply (the same as
    `onboard_trex`).

    Writes every address to `out`, including those of the token and its registries, which are
    read back from the factory and the token. Running it again sends nothing that is done.
    """
    document = json.loads((network_dir / "wallets.json").read_text(encoding="utf-8"))
    accounts = account_addresses(document)
    existing = read_addresses(out)
    client = FireflyClient(http_transport())

    def save(addresses: dict[str, str]) -> None:
        update_addresses(out, addresses)  # adds to the file; other phases' entries stay

    deployed = run_plan(
        build_plan(),
        client=client,
        load=load_artifact,
        accounts=accounts,
        code_at=get_code,
        existing=existing,
        save=save,
        log=log,
    )
    suite = read_suite(client, load_artifact, deployed, get_code)
    for name, address in suite.items():
        log(f"{name}  {address}")
    everything = {**deployed, **suite}
    save(everything)
    register_apis(client, load_artifact, suite, log)
    unpause_token(client, accounts["admin"], log)
    register_identities(client, load_artifact, everything, accounts, log)
    issuer_key = wallet_private_key(document, "admin")
    issue_claims(client, load_artifact, everything, accounts, issuer_key, log)
    mint_initial_supply(client, accounts, log)
    return everything


def onboard_trex(
    network_dir: Path,
    out: Path = DEPLOYED_ADDRESSES,
    log: Callable[[str], None] = print,
) -> None:
    """Register and verify the demo investors. Needs `deploy`; sends only what is missing."""
    document = json.loads((network_dir / "wallets.json").read_text(encoding="utf-8"))
    addresses = read_addresses(out)
    client = FireflyClient(http_transport())
    accounts = account_addresses(document)
    register_identities(client, load_artifact, addresses, accounts, log)
    issuer_key = wallet_private_key(document, "admin")
    issue_claims(client, load_artifact, addresses, accounts, issuer_key, log)
    mint_initial_supply(client, accounts, log)
