"""Read a Paladin smart-contract artifact (pure text parsing, no I/O).

Paladin ships each contract it needs as a small Kubernetes-style YAML file (a
`SmartContractDeployment`). This project does not use Kubernetes, so this reads only the fields a
deployment needs and nothing else, which avoids a YAML dependency.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

MAX_INIT_BYTES = 49_152  # EIP-3860 (Shanghai): init code of a creation transaction

_FIELD = re.compile(r"^  ([A-Za-z][A-Za-z0-9]*):(?: (.*))?$")
_NAME = re.compile(r"^  name: (\S+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class PaladinArtifact:
    name: str  # the contract's name in the operator's manifests, e.g. `noto-factory`
    abi: list[dict[str, Any]]
    bytecode: str  # 0x-prefixed init code
    sender: str  # the Paladin key label that sends the deployment, e.g. `registry.operator`
    params_json: str  # constructor arguments as the operator writes them (may be a template)
    requires: tuple[str, ...]  # contracts that must be deployed first

    @property
    def init_size(self) -> int:
        return len(self.bytecode.removeprefix("0x")) // 2


def parse_artifact_yaml(text: str) -> PaladinArtifact:
    """Read one artifact. Raises ValueError naming what is missing or wrong."""
    if "kind: SmartContractDeployment" not in text:
        raise ValueError("not a SmartContractDeployment")
    lines = text.splitlines()
    try:
        spec_at = lines.index("spec:")
    except ValueError:
        raise ValueError("the file has no spec") from None
    name = _NAME.search("\n".join(lines[:spec_at]))
    if name is None:
        raise ValueError("the file has no metadata name")

    fields: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[spec_at + 1 :]:
        if line and not line.startswith(" "):
            break  # the next top-level key (`status:`)
        match = _FIELD.match(line)
        if match:
            current = match.group(1)
            value = match.group(2) or ""
            fields[current] = [value] if value and value not in ("|", "|-") else []
        elif current is not None and line.strip():
            fields[current].append(line)

    for needed in ("abiJSON", "bytecode", "from"):
        if needed not in fields or not "".join(fields[needed]).strip():
            raise ValueError(f"the file has no {needed}")
    abi = json.loads("\n".join(row[4:] for row in fields["abiJSON"]))
    params = fields.get("paramsJSON", [])
    if len(params) == 1:
        params_json = params[0].strip().strip("'")
    else:
        params_json = "\n".join(row[4:] for row in params)
    requires = tuple(
        row.strip().removeprefix("- ") for row in fields.get("requiredContractDeployments", [])
    )
    return PaladinArtifact(
        name=name.group(1),
        abi=abi,
        bytecode=fields["bytecode"][0].strip(),
        sender=fields["from"][0].strip(),
        params_json=params_json,
        requires=requires,
    )
