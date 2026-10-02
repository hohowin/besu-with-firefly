import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.crypto import keccak

from src.core.trex.claims import (
    KYC_CLAIM_DATA,
    SCHEME_ECDSA,
    claim_data_hash,
    claim_signer,
    needs_claim,
    sign_claim,
)

KEY = "0x" + "00" * 31 + "01"  # the well-known test key; its address is below
KEY_ADDRESS = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"
OTHER_KEY = "0x" + "00" * 31 + "02"
IDENTITY = "0x" + "ab" * 20


def test_the_data_hash_is_keccak_of_the_abi_encoding_of_identity_topic_and_data() -> None:
    data = b"KYC"
    # abi.encode(address, uint256, bytes): two static words, an offset (0x60), then length and
    # the data padded to 32 bytes.
    encoded = (
        bytes(12) + bytes.fromhex("ab" * 20)
        + (1).to_bytes(32, "big")
        + (0x60).to_bytes(32, "big")
        + len(data).to_bytes(32, "big")
        + data.ljust(32, b"\0")
    )  # fmt: skip
    assert claim_data_hash(IDENTITY, 1, data) == keccak(encoded)


def test_the_signature_is_65_bytes_with_v_of_27_or_28() -> None:
    signature = bytes.fromhex(sign_claim(KEY, IDENTITY, 1, KYC_CLAIM_DATA).removeprefix("0x"))
    assert len(signature) == 65
    assert signature[64] in (27, 28)


def test_the_signature_recovers_to_the_signer_over_the_prefixed_hash() -> None:
    signature = sign_claim(KEY, IDENTITY, 1, KYC_CLAIM_DATA)
    # The ClaimIssuer contract recovers over keccak("\x19Ethereum Signed Message:\n32" + hash).
    digest = claim_data_hash(IDENTITY, 1, KYC_CLAIM_DATA)
    recovered = Account.recover_message(encode_defunct(primitive=digest), signature=signature)
    assert recovered.lower() == KEY_ADDRESS
    assert claim_signer(IDENTITY, 1, KYC_CLAIM_DATA, signature) == KEY_ADDRESS


def test_a_claim_for_another_identity_topic_or_data_does_not_recover_to_the_signer() -> None:
    signature = sign_claim(KEY, IDENTITY, 1, KYC_CLAIM_DATA)
    assert claim_signer("0x" + "cd" * 20, 1, KYC_CLAIM_DATA, signature) != KEY_ADDRESS
    assert claim_signer(IDENTITY, 2, KYC_CLAIM_DATA, signature) != KEY_ADDRESS
    assert claim_signer(IDENTITY, 1, b"other", signature) != KEY_ADDRESS


def test_another_key_signs_differently() -> None:
    mine = sign_claim(KEY, IDENTITY, 1, KYC_CLAIM_DATA)
    theirs = sign_claim(OTHER_KEY, IDENTITY, 1, KYC_CLAIM_DATA)
    assert mine != theirs
    assert claim_signer(IDENTITY, 1, KYC_CLAIM_DATA, theirs) != KEY_ADDRESS


def test_the_scheme_is_ecdsa() -> None:
    assert SCHEME_ECDSA == 1


def test_a_claim_is_only_needed_for_a_registered_account_that_is_not_yet_verified() -> None:
    assert needs_claim("anson", IDENTITY, verified=False) is True
    assert needs_claim("anson", IDENTITY, verified=True) is False
    with pytest.raises(ValueError, match="anson has no identity"):
        needs_claim("anson", None, verified=False)
