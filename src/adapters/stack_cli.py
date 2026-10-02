"""Command line for the stack: `python scripts/stack.py <command>`.

Only `init` exists so far. `up` and `reset` arrive with the Compose stack (Phase 1, Tasks 6 and 10).
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from src.adapters.besu_config import (
    BESU_IMAGE,
    AlreadyInitialisedError,
    GenerationError,
    Generator,
    docker_generator,
    init_network,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stack.py", description="Manage the Besu stack.")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser(
        "init", help="generate genesis, validator keys and static-nodes.json with Besu"
    )
    init.add_argument(
        "--network-dir",
        type=Path,
        default=REPO_ROOT / "network-config",
        help="where to write the files (default: network-config/)",
    )
    init.add_argument(
        "--besu-image", default=BESU_IMAGE, help=f"Besu image (default: {BESU_IMAGE})"
    )
    init.add_argument("--force", action="store_true", help="overwrite existing generated files")
    return parser


def main(argv: Sequence[str] | None = None, generator: Generator | None = None) -> int:
    """Run a command and return the process exit code. `generator` lets tests avoid Docker."""
    args = build_parser().parse_args(argv)
    if args.command == "init":
        try:
            result = init_network(
                args.network_dir,
                generator=generator or docker_generator(args.besu_image),
                force=args.force,
            )
        except (AlreadyInitialisedError, GenerationError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        for number, address in enumerate(result.validator_addresses, start=1):
            print(f"validator-{number}  {address}")
        print(f"wrote {len(result.files)} files to {args.network_dir}")
    return 0
