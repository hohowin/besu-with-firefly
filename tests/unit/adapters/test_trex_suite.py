from typing import Any

import pytest

from src.adapters.trex_artifacts import LoadedArtifact
from src.adapters.trex_deploy import DeployStepError
from src.adapters.trex_suite import SUITE_NAMES, read_suite
from src.core.trex.plan import Artifact

A = {n: "0x" + f"{i:02x}" * 20 for i, n in enumerate(SUITE_NAMES, start=1)}
FACTORY = "0x" + "f1" * 20


def load(artifact: Artifact) -> LoadedArtifact:
    abi = [{"type": "function", "name": "x", "inputs": []}]
    return LoadedArtifact(artifact.path, abi, "0x", 1, 1)


class FakeClient:
    """Answers `query` from a table of (address, method) to value."""

    def __init__(self, answers: dict[tuple[str, str], Any]) -> None:
        self.answers = answers
        self.asked: list[tuple[str, str, dict[str, Any]]] = []

    def generate_interface(self, abi: Any) -> dict[str, Any]:
        return {"methods": [{"name": n, "params": [], "returns": []} for n in (
            "getToken", "name", "symbol", "identityRegistry", "compliance",
            "identityStorage", "issuersRegistry", "topicsRegistry",
        )]}  # fmt: skip

    def query(self, address: str, method: Any, inputs: Any) -> Any:
        self.asked.append((address, method["name"], dict(inputs)))
        return {"": self.answers[(address, method["name"])]}


def answers() -> dict[tuple[str, str], Any]:
    return {
        (FACTORY, "getToken"): A["token"],
        (A["token"], "name"): "Coin",
        (A["token"], "symbol"): "COIN",
        (A["token"], "identityRegistry"): A["identity-registry"],
        (A["token"], "compliance"): A["modular-compliance"],
        (A["identity-registry"], "identityStorage"): A["identity-registry-storage"],
        (A["identity-registry"], "issuersRegistry"): A["trusted-issuers-registry"],
        (A["identity-registry"], "topicsRegistry"): A["claim-topics-registry"],
    }


def read(table: dict[tuple[str, str], Any], code_at: Any = lambda _a: "0x6080") -> dict[str, str]:
    return read_suite(FakeClient(table), load, {"trex-factory": FACTORY}, code_at)


def test_the_suite_addresses_are_read_from_the_factory_and_the_token_not_assumed() -> None:
    assert read(answers()) == A


def test_the_salt_is_passed_to_the_factory() -> None:
    client = FakeClient(answers())
    read_suite(client, load, {"trex-factory": FACTORY}, lambda _a: "0x6080")
    assert (FACTORY, "getToken", {"_salt": "coin"}) in client.asked


def test_a_token_that_is_not_named_coin_is_rejected() -> None:
    table = answers()
    table[(A["token"], "name")] = "Other"
    with pytest.raises(DeployStepError, match=r"token.*'Coin'.*'Other'"):
        read(table)


def test_a_token_with_another_symbol_is_rejected() -> None:
    table = answers()
    table[(A["token"], "symbol")] = "XYZ"
    with pytest.raises(DeployStepError, match=r"token.*'COIN'.*'XYZ'"):
        read(table)


def test_a_zero_token_address_means_the_suite_was_not_created() -> None:
    table = answers()
    table[(FACTORY, "getToken")] = "0x" + "00" * 20
    with pytest.raises(DeployStepError, match=r"token.*not created"):
        read(table)


def test_an_address_without_code_is_rejected() -> None:
    with pytest.raises(DeployStepError, match=r"identity-registry.*no code"):
        read(answers(), code_at=lambda a: "0x" if a == A["identity-registry"] else "0x6080")


def test_every_method_read_exists_in_the_real_artifacts() -> None:
    """The fake above answers whatever it is asked, so check the names against the real ABIs."""
    from src.adapters.trex_artifacts import ArtifactsMissingError, load_artifact

    class AbiClient:
        def __init__(self) -> None:
            self.asked: list[str] = []

        def generate_interface(self, abi: Any) -> dict[str, Any]:
            return {"methods": [{"name": e["name"]} for e in abi if e["type"] == "function"]}

        def query(self, address: str, method: Any, inputs: Any) -> Any:
            self.asked.append(method["name"])
            return {"": {"name": "Coin", "symbol": "COIN"}.get(method["name"], A["token"])}

    client = AbiClient()
    try:
        read_suite(client, load_artifact, {"trex-factory": FACTORY}, lambda _a: "0x6080")
    except ArtifactsMissingError:
        pytest.skip("run `npm ci` in contracts/ first")
    assert {"getToken", "name", "symbol", "identityRegistry", "compliance"} <= set(client.asked)
    assert {"identityStorage", "issuersRegistry", "topicsRegistry"} <= set(client.asked)
