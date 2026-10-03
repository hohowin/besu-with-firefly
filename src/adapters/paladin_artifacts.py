"""Load the vendored Paladin contract artifacts from `contracts/paladin/` (adapter)."""

import hashlib
import json
from pathlib import Path
from typing import Any

from src.core.paladin.artifacts import PaladinArtifact, parse_artifact_yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "contracts" / "paladin"

# The four contracts, in the order the Paladin operator deploys them. The file name uses
# underscores (`noto_factory`), the manifest name inside uses dashes (`noto-factory`).
CONTRACTS = ("registry", "noto", "noto_factory", "noto_factory_proxy")


def load_paladin_artifact(name: str, directory: Path = CONTRACTS_DIR) -> PaladinArtifact:
    if name not in CONTRACTS:
        raise ValueError(f"unknown Paladin contract {name!r}, expected one of {list(CONTRACTS)}")
    path = directory / f"core_v1alpha1_smartcontractdeployment_{name}.yaml"
    return parse_artifact_yaml(path.read_text(encoding="utf-8"))


def load_noto_private_abi(directory: Path = CONTRACTS_DIR) -> list[dict[str, Any]]:
    """The ABI of Noto's private calls (`mint`, `transfer`, `balanceOf`, ...)."""
    document = json.loads((directory / "INotoPrivate.json").read_text(encoding="utf-8"))
    abi: list[dict[str, Any]] = document["abi"]
    return abi


def verify_checksums(directory: Path = CONTRACTS_DIR) -> list[str]:
    """Names of the files in `SHA256SUMS` that are missing or no longer match. Empty when fine."""
    problems = []
    for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        name = name.strip().removeprefix("*")
        path = directory / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            problems.append(name)
    return problems
