"""`python scripts/stack.py deploy`: deploy the T-REX suite, create COIN, register its APIs."""

import json
from collections.abc import Callable
from pathlib import Path

from src.adapters.firefly import FireflyClient, http_transport
from src.adapters.rpc import get_code
from src.adapters.trex_apis import register_apis, unpause_token
from src.adapters.trex_artifacts import REPO_ROOT, load_artifact
from src.adapters.trex_deploy import run_plan
from src.adapters.trex_suite import read_suite
from src.core.network.wallets import account_addresses
from src.core.trex.plan import build_plan

DEPLOYED_ADDRESSES = REPO_ROOT / "deployed-addresses.json"


def deploy_trex(
    network_dir: Path,
    out: Path = DEPLOYED_ADDRESSES,
    log: Callable[[str], None] = print,
) -> dict[str, str]:
    """Deploy the T-REX infrastructure through the running FireFly and create `COIN`.

    Then registers the contract APIs `coin` and `identity-registry`, and unpauses the token.

    Writes every address to `out`, including those of the token and its registries, which are
    read back from the factory and the token. Running it again sends nothing that is done.
    """
    document = json.loads((network_dir / "wallets.json").read_text(encoding="utf-8"))
    accounts = account_addresses(document)
    existing: dict[str, str] = {}
    if out.is_file():
        existing = json.loads(out.read_text(encoding="utf-8"))
    client = FireflyClient(http_transport())

    def save(addresses: dict[str, str]) -> None:
        text = json.dumps(addresses, indent=2) + "\n"
        out.write_text(text, encoding="utf-8", newline="\n")

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
    return everything
