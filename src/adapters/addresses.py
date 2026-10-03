"""`deployed-addresses.json`: the contract addresses that `deploy` writes (adapter, file I/O).

Several phases write into the same file (T-REX through FireFly, then Paladin), so a write adds to
what is there instead of replacing it.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOYED_ADDRESSES = REPO_ROOT / "deployed-addresses.json"


def read_addresses(path: Path = DEPLOYED_ADDRESSES) -> dict[str, str]:
    """The addresses recorded so far; empty when there is no file yet."""
    if not path.is_file():
        return {}
    data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return data


def update_addresses(path: Path, updates: dict[str, str]) -> dict[str, str]:
    """Add `updates` to the file, keeping every other entry, and return the whole content."""
    merged = {**read_addresses(path), **updates}
    path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8", newline="\n")
    return merged
