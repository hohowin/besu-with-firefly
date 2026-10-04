"""Command line over FireFly: `besu-ff <command>`.

`query` reads through a registered contract API; `tx` shows an operation and its events.
Argument parsing and output only; the rules are in `src/core/firefly/`.
"""

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict
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

    tx = commands.add_parser("tx", help="show an operation and the events of its transaction")
    tx.add_argument("operation_id")
    return parser


def main(
    argv: Sequence[str] | None = None,
    port: FireflyPort | None = None,
    out: Callable[[str], None] = print,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        firefly = port or FireflyClient(http_transport())
        if args.command == "tx":
            return _tx(firefly, args, out)
        return _query(firefly, args, out)
    except (InputError, FireflyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _query(firefly: FireflyPort, args: argparse.Namespace, out: Callable[[str], None]) -> int:
    wallets = _wallets(args.network_dir) if _uses_wallet_names(args.input) else {}
    result = firefly.api_query(args.contract, args.method, parse_inputs(args.input, wallets))
    if args.json:
        out(json.dumps({"contract": args.contract, "method": args.method, "result": result}))
    else:
        out(_text(result))
    return 0


def _tx(firefly: FireflyPort, args: argparse.Namespace, out: Callable[[str], None]) -> int:
    """Show the operation as FireFly reports it; a status is printed, never judged here."""
    operation = firefly.get_operation(args.operation_id)
    events = firefly.transaction_events(operation.tx) if operation.tx else []
    if args.json:
        document = {
            "operation": {
                "id": operation.id,
                "status": operation.status,
                "tx": operation.tx,
                "error": operation.error,
            },
            "events": [asdict(event) for event in events],
        }
        out(json.dumps(document))
        return 0
    out(f"operation  {operation.id}")
    out(f"status     {operation.status}")
    if operation.tx:
        out(f"tx         {operation.tx}")
    if operation.error:
        out(f"error      {operation.error}")
    for event in events:
        out(f"event      {event.sequence}  {event.type}  {event.created}")
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
