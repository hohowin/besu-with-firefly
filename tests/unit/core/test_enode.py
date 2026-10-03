import ipaddress

import pytest

from src.core.network.enode import (
    NetworkAddressing,
    enode_url,
    normalize_public_key,
    static_nodes,
)

# Validator public key taken from the Phase 0 spike (spike/qbft/out/keys/.../key.pub).
PUBKEY = (
    "a95c41a76f3274d417b585818c3b5eee22985af86a614464b006f77a3be8de49"
    "62f2645631bd2d04c773b07258ed7784fb4b4ae683b39ed5e90d5b570a352b5b"
)


def test_enode_url_has_the_exact_expected_form() -> None:
    assert enode_url(PUBKEY, "172.28.0.11") == f"enode://{PUBKEY}@172.28.0.11:30303"


def test_enode_url_accepts_0x_prefix_and_uppercase_and_a_custom_port() -> None:
    assert enode_url("0x" + PUBKEY.upper(), "172.28.0.12", 30304) == (
        f"enode://{PUBKEY}@172.28.0.12:30304"
    )


@pytest.mark.parametrize("bad", ["", "abc", "0x" + "ab" * 63, "zz" * 64, "ab" * 65])
def test_a_public_key_that_is_not_128_hex_characters_is_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="128 hex characters"):
        normalize_public_key(bad)


def test_default_addressing_is_inside_the_subnet_and_unique() -> None:
    addressing = NetworkAddressing()
    network = ipaddress.ip_network(addressing.subnet)
    ips = addressing.all_ips()
    assert len(ips) == len(set(ips)) == 2
    assert all(ipaddress.ip_address(ip) in network for ip in ips)


def test_default_addresses_follow_the_plan() -> None:
    addressing = NetworkAddressing()
    assert addressing.validator_ip(1) == "172.28.0.11"
    assert addressing.rpc_ip("anson") == "172.28.0.21"


def test_an_address_outside_the_subnet_is_rejected() -> None:
    with pytest.raises(ValueError, match="outside"):
        NetworkAddressing(subnet="172.28.0.0/24", validator_offsets=(11, 12, 13, 300))


def test_duplicate_offsets_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        NetworkAddressing(validator_offsets=(11, 12, 13, 21))


def test_unknown_validator_or_rpc_name_is_rejected() -> None:
    addressing = NetworkAddressing()
    with pytest.raises(ValueError, match="validator"):
        addressing.validator_ip(2)
    with pytest.raises(ValueError, match="rpc"):
        addressing.rpc_ip("beatrice")  # there is a single RPC node


def test_static_nodes_lists_one_enode_per_validator_in_order() -> None:
    keys = [format(i, "x").zfill(128) for i in range(1, 5)]
    nodes = static_nodes(keys, NetworkAddressing(validator_offsets=(11, 12, 13, 14)))
    assert nodes == [
        f"enode://{keys[0]}@172.28.0.11:30303",
        f"enode://{keys[1]}@172.28.0.12:30303",
        f"enode://{keys[2]}@172.28.0.13:30303",
        f"enode://{keys[3]}@172.28.0.14:30303",
    ]


def test_static_nodes_rejects_a_key_count_that_does_not_match_the_validators() -> None:
    with pytest.raises(ValueError, match="1 validators"):
        static_nodes([PUBKEY, PUBKEY], NetworkAddressing())
