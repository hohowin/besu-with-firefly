"""Make FireFly's signer able to sign for the benchmark wallets (adapter: files and Docker).

The signer reads its keystore folder when it starts and does not notice new files, and it takes the
address from the file name, so the files are named by address like the committed ones. Existing
files are never rewritten and never removed.
"""

import json
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from src.adapters.docker_stack import REPO_ROOT, DockerStack, Runner, StackError, subprocess_runner
from src.core.firefly.keystore import keystore_files
from src.core.network.wallets import Wallet

SIGNER_DATA = REPO_ROOT / "network-config" / "firefly" / "signer-data"
SIGNER_CONTAINER = "firefly-signer"
_ETH_ACCOUNTS = '{"jsonrpc":"2.0","method":"eth_accounts","params":[],"id":1}'


def signer_accounts(runner: Runner | None = None) -> list[str]:
    """The addresses the running signer lists, lower case (asked from inside its container)."""
    command = [
        "docker", "exec", SIGNER_CONTAINER, "curl", "-s", "-X", "POST",
        "-H", "Content-Type: application/json", "--data", _ETH_ACCOUNTS, "http://localhost:8545",
    ]  # fmt: skip
    code, out, err = (runner or subprocess_runner())(command)
    if code != 0:
        raise StackError(f"`docker exec {SIGNER_CONTAINER} ...` failed ({code}): {err.strip()}")
    try:
        return [str(a).lower() for a in json.loads(out)["result"]]
    except (ValueError, KeyError, TypeError) as error:
        raise StackError(f"the signer's eth_accounts is not usable: {out[:200]!r}") from error


def load_perf_wallets(
    wallets: Sequence[Wallet],
    signer_data: Path = SIGNER_DATA,
    restart: Callable[[str], None] | None = None,
    accounts: Callable[[], list[str]] = signer_accounts,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    timeout: float = 60.0,
) -> list[str]:
    """Write the keystores that are missing and restart the signer unless it lists every wallet.

    Returns the names of the wallets whose files were written. Safe to repeat.
    """
    written = _write_missing(wallets, signer_data)
    wanted = [w.address.lower() for w in wallets]
    listed = accounts()
    if all(address in listed for address in wanted):
        return written
    (restart or DockerStack().restart)(SIGNER_CONTAINER)
    deadline = clock() + timeout
    while True:
        try:
            listed = accounts()
        except StackError:  # the signer is still starting
            listed = []
        missing = [w.name for w in wallets if w.address.lower() not in listed]
        if not missing:
            return written
        if clock() >= deadline:
            raise StackError(
                f"the signer did not list {', '.join(missing)} within {timeout:g}s of restarting"
            )
        sleep(2.0)


def _write_missing(wallets: Sequence[Wallet], signer_data: Path) -> list[str]:
    written = []
    for wallet in wallets:
        stem = wallet.address.lower().removeprefix("0x")
        if (signer_data / "keystore" / f"{stem}.toml").exists():
            continue
        for relative, content in keystore_files([wallet]).items():
            target = signer_data / relative
            if target.name == "password" and target.exists():
                continue  # one shared password file, already there
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        written.append(wallet.name)
    return written
