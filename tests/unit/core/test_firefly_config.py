import pytest

from src.core.firefly.config import (
    CHAIN_ID,
    SIGNER_BACKEND_URL,
    core_config,
    evmconnect_config,
    signer_config,
)

ADMIN = "0x7e5f4552091a69125d5dfcb7b8c2659029395bdf"


def test_core_config_is_gateway_mode_with_the_admin_as_default_key() -> None:
    text = core_config(ADMIN)
    assert f"defaultKey: {ADMIN}" in text
    assert "enabled: false" in text  # multiparty
    assert "default: default" in text
    assert "plugins: [database0, blockchain0]" in text


def test_core_config_has_no_data_exchange_or_ipfs() -> None:
    text = core_config(ADMIN).lower()
    assert "dataexchange" not in text
    assert "ipfs" not in text


def test_core_config_rejects_a_malformed_admin_address() -> None:
    with pytest.raises(ValueError, match="admin address"):
        core_config("not-an-address")


def test_evmconnect_config_runs_on_a_zero_gas_chain() -> None:
    text = evmconnect_config()
    assert "fixedGasPrice: 0" in text
    assert "mode: fixed" in text
    assert "required: 0" in text  # confirmations


def test_signer_backend_is_the_anson_rpc_node_not_the_docker_host() -> None:
    text = signer_config()
    assert SIGNER_BACKEND_URL == "http://besu-rpc-anson:8545"
    assert f"url: {SIGNER_BACKEND_URL}" in text
    assert "host.docker.internal" not in text
    assert f"chainId: {CHAIN_ID}" in text
    assert CHAIN_ID == 20260916
