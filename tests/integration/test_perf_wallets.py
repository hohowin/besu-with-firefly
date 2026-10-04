"""The benchmark wallets are loaded into FireFly's signer."""

import json

import pytest

from src.adapters.docker_stack import REPO_ROOT
from src.adapters.perf_wallets import SIGNER_DATA, load_perf_wallets, signer_accounts
from src.core.perf.wallets import derive_wallets

pytestmark = pytest.mark.integration


def test_the_signer_lists_the_perf_wallets_and_still_the_demo_wallets(stack: object) -> None:
    wallets = derive_wallets(3)
    load_perf_wallets(wallets)
    listed = signer_accounts()
    document = json.loads((REPO_ROOT / "network-config" / "wallets.json").read_text("utf-8"))
    demo = [w["address"].lower() for w in document["wallets"]]
    assert [w.address for w in wallets if w.address not in listed] == []
    assert [a for a in demo if a not in listed] == []


def test_loading_again_writes_nothing_and_does_not_restart_the_signer(stack: object) -> None:
    wallets = derive_wallets(3)
    load_perf_wallets(wallets)
    before = {p.name: p.stat().st_mtime_ns for p in (SIGNER_DATA / "keystore").iterdir()}
    restarts: list[str] = []
    assert load_perf_wallets(wallets, restart=restarts.append) == []
    assert restarts == []
    assert {p.name: p.stat().st_mtime_ns for p in (SIGNER_DATA / "keystore").iterdir()} == before
