"""Command line over FireFly: `besu-ff <command>`.

`query` reads through a registered contract API. Argument parsing and output only; the rules are
in `src/core/firefly/`.
"""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from src.adapters.addresses import REPO_ROOT
from src.adapters.firefly import FireflyClient, http_transport
from src.core.firefly.errors import FireflyError
from src.core.firefly.inputs import InputError, parse_inputs
from src.core.firefly.port import FireflyPort
from src.core.network.wallets import account_addresses


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="besu-ff", description="Drive FireFly from the shell.")
    parser.add_argument("--json", action="store_true", help="print one JSON object")
    parser.add_argument(
        "--network-dir",
        type=Path,
        default=REPO_ROOT / "network-config",
        help="where wallets.json is (default: network-config/)",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    query = commands.add_parser("query", help="read through a contract API")
    query.add_argument("method")
    query.add_argument("--contract", required=True, help="the contract API name, e.g. coin")
    query.add_argument(
        "--input",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="a method argument; VALUE may be @wallet for a wallet's address (repeatable)",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    port: FireflyPort | None = None,
    out: Callable[[str], None] = print,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        wallets = _wallets(args.network_dir) if _uses_wallet_names(args.input) else {}
        inputs = parse_inputs(args.input, wallets)
        firefly = port or FireflyClient(http_transport())
        result = firefly.api_query(args.contract, args.method, inputs)
    except (InputError, FireflyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.json:
        out(json.dumps({"contract": args.contract, "method": args.method, "result": result}))
    else:
        out(_text(result))
    return 0


def _uses_wallet_names(pairs: Sequence[str]) -> bool:
    return any(pair.partition("=")[2].startswith("@") for pair in pairs)


def _wallets(network_dir: Path) -> dict[str, str]:
    path = network_dir / "wallets.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        return account_addresses(document)
    except (OSError, ValueError) as error:
        raise InputError(f"cannot read the wallets in {path}: {error}") from error


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value)
