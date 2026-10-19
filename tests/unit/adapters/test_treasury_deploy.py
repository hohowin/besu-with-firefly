import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from src.adapters.treasury_deploy import (
    check_wiring,
    ensure_wallets,
    register_treasury_apis,
)
from src.adapters.trex_artifacts import LoadedArtifact
from src.adapters.trex_deploy import DeployStepError
from src.core.network.wallets import Wallet, build_wallets_document, derive_address
from src.core.treasury.plan import APIS, NEW_WALLETS
from src.core.trex.plan import Artifact

KEYS = {
    "admin": "0x" + "11" * 32,
    "anson": "0x" + "22" * 32,
    "ldn": "0x" + "33" * 32,
    "tor": "0x" + "44" * 32,
    "treasury": "0x" + "55" * 32,
}


def wallet(name: str) -> Wallet:
    return Wallet(name, derive_address(KEYS[name]), KEYS[name])


def write_wallets(folder: Path, names: Sequence[str]) -> Path:
    path = folder / "wallets.json"
    document = build_wallets_document([wallet(n) for n in names])
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


# ---- ensure_wallets ----


def test_the_missing_wallets_are_created_saved_and_given_to_the_signer(tmp_path: Path) -> None:
    path = write_wallets(tmp_path, ["admin", "anson"])
    loaded: list[list[str]] = []

    def load(wallets: Sequence[Wallet]) -> list[str]:
        loaded.append([w.name for w in wallets])
        return []

    accounts = ensure_wallets(tmp_path, load=load, create=wallet)
    assert set(accounts) == {"admin", "anson", *NEW_WALLETS}
    assert accounts["ldn"] == wallet("ldn").address
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert [w["name"] for w in saved["wallets"]] == ["admin", "anson", "ldn", "tor", "treasury"]
    assert loaded == [["ldn", "tor", "treasury"]]  # only the treasury wallets, not admin


def test_wallets_that_exist_are_never_replaced(tmp_path: Path) -> None:
    path = write_wallets(tmp_path, ["admin", "ldn", "tor", "treasury"])
    before = path.read_text(encoding="utf-8")

    def refuse(name: str) -> Wallet:
        raise AssertionError(f"{name} should not be created")

    ensure_wallets(tmp_path, load=lambda wallets: [], create=refuse)
    assert path.read_text(encoding="utf-8") == before


def test_only_the_missing_one_is_created(tmp_path: Path) -> None:
    write_wallets(tmp_path, ["admin", "ldn", "tor"])
    made: list[str] = []

    def create(name: str) -> Wallet:
        made.append(name)
        return wallet(name)

    ensure_wallets(tmp_path, load=lambda wallets: [], create=create)
    assert made == ["treasury"]


# ---- register and wiring ----


def load_fake(artifact: Artifact) -> LoadedArtifact:
    return LoadedArtifact(artifact.path, [{"abi": artifact.path}], "0x", 1, 1)


FR = "0x" + "03" * 20
ADDRESSES = {"cadc": "0x" + "01" * 20, "gbpc": "0x" + "02" * 20, "funding-request": FR}
ACCOUNTS = {"treasury": "0x" + "aa" * 20}


def good_answers() -> dict[tuple[str, str], str]:
    return {
        ("cadc", "controller"): FR,
        ("gbpc", "controller"): FR.upper().replace("0X", "0x"),  # the case does not matter
        ("funding-request", "treasury"): ACCOUNTS["treasury"],
        ("funding-request", "cadc"): ADDRESSES["cadc"],
        ("funding-request", "gbpc"): ADDRESSES["gbpc"],
    }


class FakeClient:
    def __init__(self, answers: Mapping[tuple[str, str], str] | None = None) -> None:
        self.interfaces: list[str] = []
        self.apis: list[tuple[str, str, str]] = []
        self.answers = answers or good_answers()

    def ensure_interface(self, name: str, version: str, abi: Sequence[Any]) -> str:
        self.interfaces.append(name)
        return f"if-{name}"

    def ensure_api(self, name: str, interface_id: str, address: str) -> str:
        self.apis.append((name, interface_id, address))
        return name

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        return self.answers[(api, method)]


def test_an_interface_and_api_per_contract() -> None:
    client = FakeClient()
    register_treasury_apis(client, load_fake, ADDRESSES, lambda _line: None)
    assert client.interfaces == [api for api, _, _ in APIS]
    assert client.apis == [
        ("cadc", "if-cadc", ADDRESSES["cadc"]),
        ("gbpc", "if-gbpc", ADDRESSES["gbpc"]),
        ("funding-request", "if-funding-request", FR),
    ]


def test_correct_wiring_passes_whatever_the_address_case() -> None:
    check_wiring(FakeClient(), ADDRESSES, ACCOUNTS)


@pytest.mark.parametrize(
    "key", [("cadc", "controller"), ("funding-request", "treasury"), ("funding-request", "gbpc")]
)
def test_a_wrong_value_is_named(key: tuple[str, str]) -> None:
    answers = good_answers()
    answers[key] = "0x" + "ff" * 20
    with pytest.raises(DeployStepError, match=f"{key[0]}.{key[1]}"):
        check_wiring(FakeClient(answers), ADDRESSES, ACCOUNTS)
