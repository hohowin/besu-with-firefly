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
from src.core.firefly.inputs import InputError, parse_inputs, resolve_identity
from src.core.firefly.invoke import run_invoke
from src.core.firefly.outcome import ComplianceRevert, Pending, Succeeded
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
    _add_input(query)

    invoke = commands.add_parser("invoke", help="write through a contract API")
    invoke.add_argument("method")
    invoke.add_argument("--contract", required=True, help="the contract API name, e.g. coin")
    invoke.add_argument("--as", dest="identity", required=True, help="the wallet that signs")
    _add_input(invoke)

    tx = commands.add_parser("tx", help="show an operation and the events of its transaction")
    tx.add_argument("operation_id")
    return parser


def _add_input(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="a method argument; VALUE may be @wallet for a wallet's address (repeatable)",
    )


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
        if args.command == "invoke":
            return _invoke(firefly, args, out)
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


def _invoke(firefly: FireflyPort, args: argparse.Namespace, out: Callable[[str], None]) -> int:
    wallets = _wallets(args.network_dir)
    key = resolve_identity(args.identity, wallets)
    inputs = parse_inputs(args.input, wallets)
    report = run_invoke(firefly, args.contract, args.method, inputs, key)
    names = {address: name for name, address in wallets.items()}
    balances = {names.get(address, address): value for address, value in report.after.items()}
    outcome = report.outcome
    if isinstance(outcome, Succeeded):
        operation = outcome.operation
        if args.json:
            out(_invoke_json(args, "succeeded", operation=operation.id, tx=operation.tx,
                             balances=balances))  # fmt: skip
            return 0
        out(f"sent       {args.method} as {args.identity}")
        out(f"operation  {operation.id}")
        if operation.tx:
            out(f"tx         {operation.tx}")
        for name, value in balances.items():
            out(f"balance    {name}  {value}")
        return 0
    if isinstance(outcome, Pending):
        status, code, label = "pending", 3, "pending"
        message = (
            f"not confirmed ({outcome.status}), so not reported as done; operation "
            f"{outcome.operation_id}, transaction {outcome.transaction_id}; "
            f"check later with: besu-ff tx {outcome.operation_id}"
        )
    elif isinstance(outcome, ComplianceRevert):
        status, code, label = "refused", 1, "error"
        message = f"refused by the contract: {outcome.reason}"
    elif outcome.operation_id:
        status, code, label = "failed", 1, "error"
        message = f"operation {outcome.operation_id} failed: {outcome.error or 'no error text'}"
    else:
        status, code, label = "failed", 1, "error"
        message = str(outcome.error)
    unchanged = None
    if report.before and report.after:
        unchanged = report.before == report.after
    if args.json:
        out(_invoke_json(args, status, message=message, balances=balances, unchanged=unchanged))
    elif unchanged is not None:
        out("balances unchanged" if unchanged else "balances CHANGED")
    print(f"{label}: {message}", file=sys.stderr)
    return code


def _invoke_json(args: argparse.Namespace, status: str, **fields: Any) -> str:
    return json.dumps(
        {"status": status, "as": args.identity, "contract": args.contract,
         "method": args.method, **fields}
    )  # fmt: skip


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
