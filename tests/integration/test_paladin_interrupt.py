"""An interrupted Paladin bootstrap is finished by running the phase again."""

import subprocess
import sys

import pytest

from src.adapters.addresses import read_addresses
from src.adapters.docker_stack import REPO_ROOT, DockerStack
from src.core.paladin.bootstrap import ADDRESS_NAMES
from tests.support.deploy import run_stack
from tests.support.paladin import PALADIN_PORTS, paladin_call
from tests.support.polling import wait_for

pytestmark = pytest.mark.integration

PHASE = "from src.adapters.paladin_command import deploy_paladin_phase; deploy_paladin_phase()"


def recorded() -> list[str]:
    return [name for name in ADDRESS_NAMES.values() if name in read_addresses()]


def test_a_bootstrap_killed_after_two_contracts_is_finished_by_running_it_again(
    stack: DockerStack,
) -> None:
    assert run_stack("reset").returncode == 0
    assert run_stack("up").returncode == 0

    process = subprocess.Popen(
        [sys.executable, "-c", PHASE],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for(
            lambda: len(recorded()) >= 2 or None,
            describe="two Paladin contracts to be deployed",
            timeout=300,
            interval=0.2,
        )
    finally:
        process.kill()
        process.wait()
    partial = read_addresses()
    assert 2 <= len(recorded()) < 4, f"the run was not interrupted part-way: {recorded()}"

    finished = subprocess.run(
        [sys.executable, "-c", PHASE],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert finished.returncode == 0, f"{finished.stdout}\n{finished.stderr}"
    final = read_addresses()
    assert len(recorded()) == 4
    for name, address in partial.items():
        assert final[name] == address, f"{name} was deployed again"
    for node in PALADIN_PORTS:
        assert paladin_call(node, "domain_listDomains") == ["noto"], node

    # The bootstrap restarted the Paladin nodes; leave the stack healthy for the next tests.
    stack.up(wait_timeout=300)
