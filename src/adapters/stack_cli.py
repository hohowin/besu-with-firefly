"""Command line for the stack: `python scripts/stack.py <command>`.

`init`, `up`, `deploy`, `onboard`, `noto-demo` and `reset`.
"""

import argparse
import shutil
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from src.adapters.addresses import DEPLOYED_ADDRESSES
from src.adapters.besu_config import (
    BESU_IMAGE,
    AlreadyInitialisedError,
    GenerationError,
    Generator,
    docker_generator,
    init_network,
)
from src.adapters.docker_stack import DockerStack, StackError
from src.adapters.firefly import FireflyError
from src.adapters.paladin_command import deploy_paladin_phase
from src.adapters.paladin_demo import DemoFailed, NotDeployed, noto_demo
from src.adapters.paladin_deploy import PaladinBootstrapError
from src.adapters.paladin_files import CertMaker, docker_cert_maker, seed_runtime
from src.adapters.rpc import chain_heights_reader
from src.adapters.trex_artifacts import ArtifactsMissingError
from src.adapters.trex_command import deploy_trex, onboard_trex
from src.adapters.trex_deploy import DeployStepError
from src.core.network.health import ContainerState
from src.core.paladin.rpc import PaladinRpcError

REPO_ROOT = Path(__file__).resolve().parents[2]
PALADIN_SOURCE = REPO_ROOT / "network-config" / "paladin"  # committed base configs and certificates
PALADIN_RUNTIME = REPO_ROOT / "paladin-runtime"  # what Compose mounts; `deploy` adds the domain


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

    up = commands.add_parser("up", help="start the stack and wait until every service is healthy")
    up.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="seconds to wait for healthy containers and a moving chain (default: 300)",
    )
    deploy = commands.add_parser(
        "deploy", help="deploy the T-REX contracts through FireFly (the stack must be up)"
    )
    deploy.add_argument(
        "--network-dir",
        type=Path,
        default=REPO_ROOT / "network-config",
        help="where wallets.json is (default: network-config/)",
    )
    onboard = commands.add_parser(
        "onboard", help="register the demo investors (needs deploy; sends only what is missing)"
    )
    onboard.add_argument(
        "--network-dir",
        type=Path,
        default=REPO_ROOT / "network-config",
        help="where wallets.json is (default: network-config/)",
    )
    commands.add_parser(
        "noto-demo", help="mint and transfer a private Noto token and show what each node sees"
    )
    commands.add_parser(
        "reset", help="remove the containers and volumes, so the chain restarts at genesis"
    )
    return parser


class Stack(Protocol):
    def up(self, wait_timeout: float) -> list[ContainerState]: ...

    def reset(self) -> list[str]: ...


def main(
    argv: Sequence[str] | None = None,
    generator: Generator | None = None,
    cert_maker: CertMaker | None = None,
    stack: Stack | None = None,
    deployer: Callable[[Path], dict[str, str]] | None = None,
    onboarder: Callable[[Path], None] | None = None,
    paladin_deployer: Callable[[], None] | None = None,
    demo_runner: Callable[[], str] | None = None,
    addresses_file: Path = DEPLOYED_ADDRESSES,
    paladin_source: Path | None = None,
    paladin_runtime: Path | None = None,
) -> int:
    """Run a command and return the process exit code.

    Tests inject `generator`, `cert_maker`, `stack`, `deployer`, `onboarder`, `paladin_deployer`,
    `demo_runner`, `addresses_file`, `paladin_source` and `paladin_runtime`.
    """
    args = build_parser().parse_args(argv)
    if args.command == "init":
        try:
            result = init_network(
                args.network_dir,
                generator=generator or docker_generator(args.besu_image),
                cert_maker=cert_maker or docker_cert_maker(),
                force=args.force,
            )
        except (AlreadyInitialisedError, GenerationError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        for number, address in enumerate(result.validator_addresses, start=1):
            print(f"validator-{number}  {address}")
        print(f"wrote {len(result.files)} files to {args.network_dir}")
    if args.command == "up":
        try:
            seed_runtime(paladin_source or PALADIN_SOURCE, paladin_runtime or PALADIN_RUNTIME)
        except FileNotFoundError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        try:
            states = (stack or DockerStack(chain_heights=chain_heights_reader())).up(
                wait_timeout=args.timeout
            )
        except StackError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        for state in states:
            print(f"{state.service}  {state.state}  {state.health or '-'}")
    if args.command == "deploy":
        try:
            (deployer or deploy_trex)(args.network_dir)
        except (DeployStepError, ArtifactsMissingError, OSError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        try:
            (paladin_deployer or deploy_paladin_phase)()
        except (PaladinBootstrapError, PaladinRpcError, OSError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    if args.command == "onboard":
        try:
            (onboarder or onboard_trex)(args.network_dir)
        except (DeployStepError, FireflyError, OSError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    if args.command == "noto-demo":
        try:
            (demo_runner or noto_demo)()
        except (NotDeployed, DemoFailed, PaladinRpcError, OSError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    if args.command == "reset":
        try:
            removed = (stack or DockerStack()).reset()
        except StackError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        if removed:
            print(f"removed {len(removed)} containers and their volumes: {', '.join(removed)}")
        else:
            print("nothing to remove")
        if addresses_file.exists():  # the addresses it holds belong to the chain that is gone
            addresses_file.unlink()
            print(f"removed {addresses_file.name}")
        runtime = paladin_runtime or PALADIN_RUNTIME
        if runtime.exists():  # its config may name contracts that were on the chain that is gone
            shutil.rmtree(runtime)
            print(f"removed {runtime.name}")
    return 0
