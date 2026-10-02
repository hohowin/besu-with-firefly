"""KYC claims for OnchainID identities (pure computation).

An OnchainID `ClaimIssuer` accepts a claim when its signature, over
`keccak256(abi.encode(identity, topic, data))` with the Ethereum signed-message prefix, recovers to
a key that has the claim (or management) purpose on the issuer.
"""

from eth_abi.abi import encode
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_utils.crypto import keccak

SCHEME_ECDSA = 1
KYC_CLAIM_DATA = b"KYC verified"  # what the issuer attests; any bytes would do for the demo


def claim_data_hash(identity: str, topic: int, data: bytes) -> bytes:
    """`keccak256(abi.encode(identity, topic, data))`, as the ClaimIssuer contract computes it."""
    return keccak(encode(["address", "uint256", "bytes"], [identity, topic, data]))


def sign_claim(private_key: str, identity: str, topic: int, data: bytes) -> str:
    """Sign a claim as the issuer's key. Returns `0x` plus r, s and v (65 bytes, v 27 or 28)."""
    digest = claim_data_hash(identity, topic, data)
    signed = Account.sign_message(encode_defunct(primitive=digest), private_key)
    return "0x" + bytes(signed.signature).hex()


def claim_signer(identity: str, topic: int, data: bytes, signature: str) -> str:
    """The address a claim signature recovers to (lower case), for checks and tests."""
    digest = claim_data_hash(identity, topic, data)
    recovered = Account.recover_message(encode_defunct(primitive=digest), signature=signature)
    return str(recovered).lower()


def needs_claim(account: str, identity: str | None, verified: bool) -> bool:
    """A claim is needed for a registered account that is not verified yet."""
    if verified:
        return False
    if identity is None:
        raise ValueError(f"{account} has no identity, so it cannot hold a claim")
    return True
