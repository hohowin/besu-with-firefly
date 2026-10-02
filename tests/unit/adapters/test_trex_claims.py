from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from src.adapters.trex_artifacts import LoadedArtifact
from src.adapters.trex_deploy import DeployStepError
from src.adapters.trex_onboard import issue_claims
from src.core.firefly.operations import Operation
from src.core.trex.claims import KYC_CLAIM_DATA, claim_signer
from src.core.trex.plan import Artifact

ZERO = "0x" + "00" * 20
ADMIN_KEY = "0x" + "00" * 31 + "01"
ADMIN = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"
ACCOUNTS = {"admin": ADMIN, "anson": "0x" + "a1" * 20, "beatrice": "0x" + "b1" * 20}
ADDRESSES = {"claim-issuer": "0x" + "c1" * 20, "id-factory": "0x" + "f0" * 20}
IDENTITIES = {ACCOUNTS["anson"]: "0x" + "11" * 20, ACCOUNTS["beatrice"]: "0x" + "22" * 20}


def load(artifact: Artifact) -> LoadedArtifact:
    return LoadedArtifact(artifact.path, [{"type": "function", "name": "x"}], "0x", 1, 1)


class FakeChain:
    def __init__(self, identities: Mapping[str, str] | None = None) -> None:
        self.identities = dict(IDENTITIES if identities is None else identities)
        self.verified: set[str] = set()
        self.writes: list[tuple[str, str, dict[str, Any], str | None]] = []

    def transaction_operations(self, transaction_id: str) -> list[Operation]:
        return [Operation("op-old", "Succeeded")]

    def generate_interface(self, abi: Sequence[Any]) -> dict[str, Any]:
        return {"methods": [{"name": n} for n in ("getIdentity", "addClaim")]}

    def query(self, address: str, method: Mapping[str, Any], inputs: Mapping[str, Any]) -> Any:
        return {"": self.identities.get(inputs["_wallet"], ZERO)}

    def invoke(self, address: str, method: Mapping[str, Any], inputs: Mapping[str, Any],
               key: str | None = None, idempotency_key: str | None = None,
               timeout: float = 0) -> Operation:
        assert method["name"] == "addClaim"
        self.writes.append((address, "addClaim", dict(inputs), key))
        owner = next(w for w, i in self.identities.items() if i == address)
        self.verified.add(owner)
        return Operation("op", "Succeeded")

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        assert (api, method) == ("identity-registry", "isVerified")
        return inputs["_userAddress"] in self.verified

    def api_invoke(self, api: str, method: str, inputs: Mapping[str, Any], key: str | None = None,
                   idempotency_key: str | None = None, timeout: float = 0) -> Operation:
        raise AssertionError("claims are added to the identity, not through the registry API")


def run(chain: FakeChain) -> None:
    issue_claims(chain, load, ADDRESSES, ACCOUNTS, ADMIN_KEY, lambda _line: None)


def test_each_investor_adds_a_claim_signed_by_the_admin_issuer_to_their_own_identity() -> None:
    chain = FakeChain()
    run(chain)
    assert [(w[0], w[3]) for w in chain.writes] == [
        (IDENTITIES[ACCOUNTS["anson"]], ACCOUNTS["anson"]),
        (IDENTITIES[ACCOUNTS["beatrice"]], ACCOUNTS["beatrice"]),
    ]  # sent to the identity, signed (as sender) by the identity's owner
    assert chain.verified == {ACCOUNTS["anson"], ACCOUNTS["beatrice"]}


def test_the_claim_input_names_the_issuer_the_topic_and_a_signature_from_the_admin_key() -> None:
    chain = FakeChain()
    run(chain)
    address, _method, inputs, _key = chain.writes[0]
    assert inputs["_topic"] == 1
    assert inputs["_scheme"] == 1
    assert inputs["_issuer"] == ADDRESSES["claim-issuer"]
    assert inputs["_data"] == "0x" + KYC_CLAIM_DATA.hex()
    assert inputs["_uri"] == ""
    assert claim_signer(address, 1, KYC_CLAIM_DATA, inputs["_signature"]) == ADMIN


def test_a_second_run_sends_nothing() -> None:
    chain = FakeChain()
    run(chain)
    run(chain)
    assert len(chain.writes) == 2


def test_an_already_verified_account_is_skipped() -> None:
    chain = FakeChain()
    chain.verified.add(ACCOUNTS["anson"])
    run(chain)
    assert [w[3] for w in chain.writes] == [ACCOUNTS["beatrice"]]


def test_an_account_without_an_identity_cannot_get_a_claim() -> None:
    chain = FakeChain(identities={ACCOUNTS["beatrice"]: IDENTITIES[ACCOUNTS["beatrice"]]})
    with pytest.raises(DeployStepError, match=r"anson.*no identity"):
        run(chain)
    assert chain.writes == []
