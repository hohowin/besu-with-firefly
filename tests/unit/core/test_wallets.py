import pytest

from src.core.network.wallets import Wallet, build_wallets_document, derive_address, verify_wallet

# Well-known Ethereum test vector (from the web3 documentation).
VECTOR_KEY = "0x4c0883a69102937d6231471b5dbb6204fe5129617082792ae468d01a3f362318"
VECTOR_ADDRESS = "0x2c7536e3605d9c16a7a3d7b1898e529396a65c23"


def test_derive_address_matches_the_known_vector_in_lowercase() -> None:
    assert derive_address(VECTOR_KEY) == VECTOR_ADDRESS


def test_derive_address_accepts_a_key_without_the_prefix() -> None:
    assert derive_address(VECTOR_KEY.removeprefix("0x")) == VECTOR_ADDRESS


def test_derive_address_rejects_a_malformed_key() -> None:
    with pytest.raises(ValueError, match="private key"):
        derive_address("0x1234")


def test_verify_wallet_accepts_a_matching_pair() -> None:
    verify_wallet(Wallet("admin", VECTOR_ADDRESS, VECTOR_KEY))


def test_verify_wallet_rejects_a_mismatched_address() -> None:
    other = "0x" + "11" * 20
    with pytest.raises(ValueError, match="does not match"):
        verify_wallet(Wallet("admin", other, VECTOR_KEY))


def test_document_lists_every_wallet_with_a_demo_notice() -> None:
    wallets = [Wallet("admin", VECTOR_ADDRESS, VECTOR_KEY)]
    document = build_wallets_document(wallets)
    assert "demo" in document["notice"].lower()
    assert document["wallets"] == [
        {"name": "admin", "address": VECTOR_ADDRESS, "privateKey": VECTOR_KEY}
    ]


def test_document_rejects_duplicate_and_empty_names() -> None:
    wallet = Wallet("admin", VECTOR_ADDRESS, VECTOR_KEY)
    with pytest.raises(ValueError, match="unique"):
        build_wallets_document([wallet, wallet])
    with pytest.raises(ValueError, match="name"):
        build_wallets_document([Wallet("", VECTOR_ADDRESS, VECTOR_KEY)])


def test_document_rejects_a_wallet_whose_address_does_not_match_its_key() -> None:
    with pytest.raises(ValueError, match="does not match"):
        build_wallets_document([Wallet("admin", "0x" + "11" * 20, VECTOR_KEY)])


def test_account_addresses_maps_each_wallet_name_to_its_address() -> None:
    from src.core.network.wallets import account_addresses

    document = {
        "wallets": [
            {"name": "admin", "address": "0x" + "aa" * 20, "privateKey": "0x01"},
            {"name": "anson", "address": "0x" + "bb" * 20, "privateKey": "0x02"},
        ]
    }
    assert account_addresses(document) == {"admin": "0x" + "aa" * 20, "anson": "0x" + "bb" * 20}


def test_account_addresses_rejects_a_document_without_wallets() -> None:
    from src.core.network.wallets import account_addresses

    with pytest.raises(ValueError, match="no wallets"):
        account_addresses({"notice": "x"})
