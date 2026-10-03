"""The Paladin phase of `python scripts/stack.py deploy` (adapter: wires the real pieces)."""

from collections.abc import Callable
from pathlib import Path

from src.adapters.addresses import DEPLOYED_ADDRESSES, read_addresses, update_addresses
from src.adapters.docker_stack import DockerStack
from src.adapters.paladin import PALADIN_NODES, PaladinClient, http_transport
from src.adapters.paladin_artifacts import load_paladin_artifact
from src.adapters.paladin_deploy import deploy_paladin
from src.adapters.rpc import get_code

REPO_ROOT = Path(__file__).resolve().parents[2]
PALADIN_SOURCE = REPO_ROOT / "network-config" / "paladin"
PALADIN_RUNTIME = REPO_ROOT / "paladin-runtime"


def deploy_paladin_phase(
    out: Path = DEPLOYED_ADDRESSES,
    source: Path = PALADIN_SOURCE,
    runtime: Path = PALADIN_RUNTIME,
    log: Callable[[str], None] = print,
) -> dict[str, str]:
    """Deploy the registry and Noto contracts, give the nodes their domain, restart them.

    Writes the four addresses into `out` as they appear. Running it again sends nothing that is
    done and restarts no node that is already right.
    """

    def save(updates: dict[str, str]) -> None:
        update_addresses(out, updates)

    return deploy_paladin(
        PaladinClient(PALADIN_NODES, http_transport()),
        load=load_paladin_artifact,
        source=source,
        runtime=runtime,
        existing=read_addresses(out),
        code_at=get_code,
        save=save,
        restart=DockerStack().restart,
        log=log,
    )
