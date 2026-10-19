"""Read the committed treasury contract artifacts from `contracts/treasury/compiled/` (adapter).

`SHA256SUMS` sits next to them; a file that does not match its checksum is refused, so the code
that runs on the chain is the code that was reviewed and tested.
"""

import hashlib
import json
from pathlib import Path

from src.adapters.trex_artifacts import REPO_ROOT, ArtifactsMissingError, LoadedArtifact
from src.core.trex.plan import Artifact

COMPILED = REPO_ROOT / "contracts" / "treasury" / "compiled"


class ChecksumError(Exception):
    """A compiled artifact does not match `SHA256SUMS`."""


def load_treasury_artifact(artifact: Artifact, folder: Path = COMPILED) -> LoadedArtifact:
    if artifact.package != "treasury":
        raise ValueError(f"{artifact.package!r} is not a treasury artifact")
    path = folder / artifact.path
    if not path.is_file():
        raise ArtifactsMissingError(
            f"{path} not found. Run `npm run build` in contracts/treasury/ and commit compiled/."
        )
    raw = path.read_bytes()
    _check(folder, artifact.path, raw)
    data = json.loads(raw)
    return LoadedArtifact(
        name=data["contractName"],
        abi=data["abi"],
        bytecode=data["bytecode"],
        deployed_size=int(data["deployedBytecodeBytes"]),
        init_size=len(data["bytecode"].removeprefix("0x")) // 2,
    )


def _check(folder: Path, name: str, raw: bytes) -> None:
    sums = folder / "SHA256SUMS"
    if not sums.is_file():
        raise ChecksumError(f"{sums} not found")
    expected = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        digest, _, file = line.partition(" *")
        if digest and file:
            expected[file] = digest
    if name not in expected:
        raise ChecksumError(f"{name} is not listed in SHA256SUMS")
    if hashlib.sha256(raw).hexdigest() != expected[name]:
        raise ChecksumError(f"{name} does not match SHA256SUMS: rebuild and commit compiled/")
