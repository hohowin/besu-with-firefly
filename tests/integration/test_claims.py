"""KYC claims: who is verified, and that the ClaimIssuer contract itself accepts the signature."""

import json
from typing import Any

import pytest
from eth_abi.abi import encode
from eth_utils.crypto import keccak

from src.adapters.docker_stack import REPO_ROOT
from src.core.trex.claims import KYC_CLAIM_DATA, sign_claim
from src.core.trex.plan import KYC_TOPIC
from tests.support.deploy import abi_of
from tests.support.firefly import ff_post, ff_query

pytestmark = pytest.mark.integration

NS = "/api/v1/namespaces/default"


def wallets() -> dict[str, dict[str, str]]:
    document = json.loads((REPO_ROOT / "network-config" / "wallets.json").read_text("utf-8"))
    return {w["name"]: w for w in document["wallets"]}


def is_verified(address: str) -> bool:
    path = f"{NS}/apis/identity-registry/query/isVerified"
    answer = ff_post(path, {"input": {"_userAddress": address}})
    return bool(answer["output"])


def identity_of(deployed: dict[str, str], wallet: str) -> str:
    abi = abi_of("id-factory")
    answer = ff_query(deployed["id-factory"], abi, "getIdentity", {"_wallet": wallet})
    return str(next(iter(answer.values()))).lower()


def claim_valid(deployed: dict[str, str], identity: str, signature: str) -> bool:
    answer: dict[str, Any] = ff_query(
        deployed["claim-issuer"],
        abi_of("claim-issuer"),
        "isClaimValid",
        {
            "_identity": identity,
            "claimTopic": KYC_TOPIC,
            "sig": signature,
            "data": "0x" + KYC_CLAIM_DATA.hex(),
        },
    )
    return bool(next(iter(answer.values())))


def test_anson_and_beatrice_are_verified_and_admin_is_not(deployed: dict[str, str]) -> None:
    accounts = wallets()
    assert is_verified(accounts["anson"]["address"]) is True
    assert is_verified(accounts["beatrice"]["address"]) is True
    assert is_verified(accounts["admin"]["address"]) is False


def test_the_claim_stored_on_the_identity_is_accepted_by_the_claim_issuer(
    deployed: dict[str, str],
) -> None:
    accounts = wallets()
    for name in ("anson", "beatrice"):
        identity = identity_of(deployed, accounts[name]["address"])
        claim_id = keccak(encode(["address", "uint256"], [deployed["claim-issuer"], KYC_TOPIC]))
        stored = ff_query(
            identity,
            abi_of("identity-implementation"),
            "getClaim",
            {"_claimId": "0x" + claim_id.hex()},
        )
        signature = stored["signature"]
        assert stored["issuer"].lower() == deployed["claim-issuer"]
        assert claim_valid(deployed, identity, signature) is True, name


def test_a_signature_from_a_key_the_issuer_does_not_know_is_rejected(
    deployed: dict[str, str],
) -> None:
    accounts = wallets()
    identity = identity_of(deployed, accounts["anson"]["address"])
    forged = sign_claim(accounts["beatrice"]["privateKey"], identity, KYC_TOPIC, KYC_CLAIM_DATA)
    assert claim_valid(deployed, identity, forged) is False


def test_the_admin_signature_for_the_right_identity_is_accepted(deployed: dict[str, str]) -> None:
    accounts = wallets()
    identity = identity_of(deployed, accounts["anson"]["address"])
    genuine = sign_claim(accounts["admin"]["privateKey"], identity, KYC_TOPIC, KYC_CLAIM_DATA)
    assert claim_valid(deployed, identity, genuine) is True
