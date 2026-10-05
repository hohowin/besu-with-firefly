"""Read contract ABIs and bytecode from the pinned npm packages in `contracts/` (adapter).

Nothing is compiled: the packages ship compiled artifacts. Install them with `npm ci` in
`contracts/`.
"""

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.trex.plan import Artifact

REPO_ROOT = Path(__file__).resolve().parents[2]


def contracts_node_modules(env: Mapping[str, str] = os.environ) -> Path:
    """Where the contract packages are: `CONTRACTS_NODE_MODULES`, else `contracts/node_modules`.

    The deployer container keeps the packages outside the repository folder, because it mounts
    that folder from the host and the mount would hide anything baked in beneath it.
    """
    if "CONTRACTS_NODE_MODULES" not in env:
        return REPO_ROOT / "contracts" / "node_modules"
    value = env["CONTRACTS_NODE_MODULES"].strip()
    if not value:
        raise ValueError("CONTRACTS_NODE_MODULES is set but blank")
    return Path(value)


NODE_MODULES = contracts_node_modules()

# Folder, below node_modules, that holds each package's `contracts/` artifacts.
_PACKAGE_ARTIFACTS = {
    "t-rex": Path("@tokenysolutions") / "t-rex" / "artifacts" / "contracts",
    "onchainid": Path("@onchain-id") / "solidity" / "artifacts" / "contracts",
}


class ArtifactsMissingError(Exception):
    """The npm packages with the compiled contracts are not installed."""


@dataclass(frozen=True)
class LoadedArtifact:
    name: str
    abi: list[dict[str, Any]]
    bytecode: str  # 0x-prefixed init code, as sent in a deploy
    deployed_size: int  # bytes of runtime code
    init_size: int  # bytes of init code


def load_artifact(artifact: Artifact, modules: Path = NODE_MODULES) -> LoadedArtifact:
    folder = _PACKAGE_ARTIFACTS.get(artifact.package)
    if folder is None:
        raise ValueError(f"unknown artifact package {artifact.package!r}")
    path = modules / folder / artifact.path
    if not path.is_file():
        raise ArtifactsMissingError(
            f"{path} not found. Run `npm ci` in contracts/ to install the pinned packages."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return LoadedArtifact(
        name=data["contractName"],
        abi=data["abi"],
        bytecode=data["bytecode"],
        deployed_size=_byte_length(data["deployedBytecode"]),
        init_size=_byte_length(data["bytecode"]),
    )


def _byte_length(hex_code: str) -> int:
    return (len(hex_code.removeprefix("0x"))) // 2
