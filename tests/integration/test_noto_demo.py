"""`stack.py noto-demo` tells the whole Noto story on the live stack."""

import pytest

from tests.support.deploy import run_stack

pytestmark = pytest.mark.integration


def test_the_demo_prints_the_balances_and_each_nodes_view(deployed: dict[str, str]) -> None:
    result = run_stack("noto-demo")
    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
    out = result.stdout
    assert "balance anson@node2" in out and out.count(" 60") >= 1
    assert "balance beatrice@node3" in out
    assert "node3 (Beatrice) sees coins [40]" in out
    assert "node1 (notary) sees coins [40, 60, 100]" in out
    assert "privacy ok" in out


def test_each_run_deploys_a_new_token(deployed: dict[str, str]) -> None:
    tokens = []
    for _ in range(2):
        result = run_stack("noto-demo")
        assert result.returncode == 0, result.stderr
        first = result.stdout.splitlines()[0]
        tokens.append(first.split()[2])
    assert tokens[0] != tokens[1]
