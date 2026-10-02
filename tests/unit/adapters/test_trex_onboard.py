from collections.abc import Mapping, Sequence
from typing import Any

from src.adapters.trex_artifacts import LoadedArtifact
from src.adapters.trex_onboard import register_identities
from src.core.firefly.operations import Operation
from src.core.trex.plan import Artifact

ZERO = "0x" + "00" * 20
ACCOUNTS = {
    "admin": "0x" + "aa" * 20,
    "anson": "0x" + "a1" * 20,
    "beatrice": "0x" + "b1" * 20,
}
ID_FACTORY = "0x" + "f0" * 20


def load(artifact: Artifact) -> LoadedArtifact:
    return LoadedArtifact(artifact.path, [{"type": "function", "name": "x"}], "0x", 1, 1)


class FakeChain:
    """A tiny stateful stand-in for FireFly: an identity factory and an identity registry."""

    def __init__(self) -> None:
        self.identities: dict[str, str] = {}
        self.registered: dict[str, tuple[str, int]] = {}
        self.writes: list[tuple[str, str, dict[str, Any], str | None]] = []

    def transaction_operations(self, transaction_id: str) -> list[Operation]:
        return [Operation("op-old", "Succeeded")]

    def generate_interface(self, abi: Sequence[Any]) -> dict[str, Any]:
        return {"methods": [{"name": n} for n in ("getIdentity", "createIdentity")]}

    def query(self, address: str, method: Mapping[str, Any], inputs: Mapping[str, Any]) -> Any:
        assert address == ID_FACTORY and method["name"] == "getIdentity"
        return {"": self.identities.get(inputs["_wallet"], ZERO)}

    def invoke(self, address: str, method: Mapping[str, Any], inputs: Mapping[str, Any],
               key: str | None = None, idempotency_key: str | None = None,
               timeout: float = 0) -> Operation:
        assert address == ID_FACTORY and method["name"] == "createIdentity"
        self.writes.append(("id-factory", "createIdentity", dict(inputs), key))
        wallet = inputs["_wallet"]
        self.identities[wallet] = "0x" + f"{len(self.identities) + 1:02x}" * 20
        return Operation("op", "Succeeded")

    def api_query(self, api: str, method: str, inputs: Mapping[str, Any]) -> Any:
        assert (api, method) == ("identity-registry", "contains")
        return inputs["_userAddress"] in self.registered

    def api_invoke(self, api: str, method: str, inputs: Mapping[str, Any], key: str | None = None,
                   idempotency_key: str | None = None, timeout: float = 0) -> Operation:
        assert (api, method) == ("identity-registry", "registerIdentity")
        self.writes.append((api, method, dict(inputs), key))
        self.registered[inputs["_userAddress"]] = (inputs["_identity"], inputs["_country"])
        return Operation("op", "Succeeded")


def run(chain: FakeChain) -> None:
    register_identities(chain, load, {"id-factory": ID_FACTORY}, ACCOUNTS, lambda _line: None)


def test_anson_and_beatrice_get_an_identity_and_are_registered_as_admin() -> None:
    chain = FakeChain()
    run(chain)
    assert set(chain.identities) == {ACCOUNTS["anson"], ACCOUNTS["beatrice"]}
    assert set(chain.registered) == {ACCOUNTS["anson"], ACCOUNTS["beatrice"]}
    assert ACCOUNTS["admin"] not in chain.registered
    assert all(write[3] == ACCOUNTS["admin"] for write in chain.writes)


def test_each_wallet_is_registered_with_its_own_identity_and_a_country() -> None:
    chain = FakeChain()
    run(chain)
    for wallet, (identity, country) in chain.registered.items():
        assert identity == chain.identities[wallet]
        assert country == 124


def test_the_identity_salt_is_the_account_name() -> None:
    chain = FakeChain()
    run(chain)
    salts = [w[2]["_salt"] for w in chain.writes if w[1] == "createIdentity"]
    assert salts == ["anson", "beatrice"]


def test_a_second_run_sends_nothing() -> None:
    chain = FakeChain()
    run(chain)
    sent = len(chain.writes)
    run(chain)
    assert len(chain.writes) == sent == 4  # two identities and two registrations


def test_an_account_that_already_has_an_identity_is_only_registered() -> None:
    chain = FakeChain()
    chain.identities[ACCOUNTS["anson"]] = "0x" + "77" * 20
    run(chain)
    creates = [w[2]["_wallet"] for w in chain.writes if w[1] == "createIdentity"]
    assert creates == [ACCOUNTS["beatrice"]]
    assert chain.registered[ACCOUNTS["anson"]][0] == "0x" + "77" * 20


def test_a_timeout_while_creating_an_identity_is_retried_and_the_accepted_write_is_used() -> None:
    from src.adapters.firefly import AlreadySubmitted, FireflyError

    class Flaky(FakeChain):
        def __init__(self) -> None:
            super().__init__()
            self.attempts: list[str | None] = []

        def invoke(self, address: str, method: Mapping[str, Any], inputs: Mapping[str, Any],
                   key: str | None = None, idempotency_key: str | None = None,
                   timeout: float = 0) -> Operation:
            self.attempts.append(idempotency_key)
            if len(self.attempts) == 1:  # the request timed out, but FireFly did accept it
                super().invoke(address, method, inputs, key, idempotency_key, timeout)
                raise FireflyError("HTTP 500: Post x: context deadline exceeded")
            raise AlreadySubmitted("tx-first")

    chain = Flaky()
    register_identities(
        chain, load, {"id-factory": ID_FACTORY}, ACCOUNTS, lambda _line: None,
        sleep=lambda _s: None,
    )  # fmt: skip
    # The retry used the same key and found the write already accepted: nothing was sent twice.
    assert chain.attempts[:2] == ["trex-createIdentity-anson", "trex-createIdentity-anson"]
    assert ACCOUNTS["anson"] in chain.registered
