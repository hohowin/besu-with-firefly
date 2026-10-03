"""Run `python scripts/stack.py deploy` from a test."""

import subprocess
import sys

from src.adapters.docker_stack import REPO_ROOT
from src.adapters.trex_artifacts import load_artifact
from src.core.trex.plan import Deploy, build_plan


def run_deploy() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "stack.py"), "deploy"],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )


def abi_of(name: str) -> list[dict[str, object]]:
    """The ABI of a contract in the deploy plan, from the pinned artifacts."""
    step = next(s for s in build_plan() if isinstance(s, Deploy) and s.name == name)
    return load_artifact(step.artifact).abi


def run_stack(*args: str) -> subprocess.CompletedProcess[str]:
    """Run `python scripts/stack.py <args>`."""
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "stack.py"), *args],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
