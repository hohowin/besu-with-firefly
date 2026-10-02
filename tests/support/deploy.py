"""Run `python scripts/stack.py deploy` from a test."""

import subprocess
import sys

from src.adapters.docker_stack import REPO_ROOT


def run_deploy() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "stack.py"), "deploy"],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
