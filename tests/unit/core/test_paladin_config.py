import pytest
from eth_account import Account

from src.core.paladin.config import (
    GRPC_PORT,
    NODES,
    RPC_HTTP_PORT,
    RPC_WS_PORT,
    base_config,
    postgres_init_sql,
    validate_mnemonic,
)

Account.enable_unaudited_hdwallet_features()
_, PHRASE = Account.create_with_mnemonic(num_words=12)


def test_the_three_nodes_are_notary_anson_and_beatrice() -> None:
    assert NODES == ("node1", "node2", "node3")


def test_the_base_config_names_the_node_and_its_own_database() -> None:
    text = base_config("node2", PHRASE)
    assert "nodeName: node2\n" in text
    assert "@paladin-postgres:5432/node2?sslmode=disable" in text
    assert "node1" not in text and "node3" not in text


def test_the_base_config_reaches_the_single_rpc_node_over_http_and_websocket() -> None:
    text = base_config("node1", PHRASE)
    assert "url: http://besu-rpc-anson:8545" in text
    assert "url: ws://besu-rpc-anson:8546" in text


def test_the_base_config_has_the_rpc_server_and_the_grpc_transport_with_mutual_tls() -> None:
    text = base_config("node3", PHRASE)
    assert f"port: {RPC_HTTP_PORT}" in text and f"port: {RPC_WS_PORT}" in text
    assert (RPC_HTTP_PORT, RPC_WS_PORT, GRPC_PORT) == (8548, 8549, 9000)
    assert "externalHostname: paladin-node3" in text
    assert "enabled: true" in text and "clientAuth: true" in text
    for path in ("/certs/tls.crt", "/certs/tls.key", "/certs/ca.crt"):
        assert path in text


def test_the_base_config_has_no_domain_or_registry_because_their_contracts_do_not_exist_yet() -> (
    None
):
    text = base_config("node1", PHRASE)
    assert "domains:" not in text
    assert "registries:" not in text


def test_the_base_config_uses_the_mnemonic_as_the_wallet_seed_and_logs_at_info() -> None:
    text = base_config("node1", PHRASE)
    assert f'inline: "{PHRASE}"' in text
    assert "type: bip32" in text
    assert "level: info" in text


def test_an_unknown_node_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown node"):
        base_config("node4", PHRASE)


def test_a_mnemonic_must_be_twelve_valid_words() -> None:
    validate_mnemonic(PHRASE)
    with pytest.raises(ValueError, match="12 words"):
        validate_mnemonic("one two three")
    with pytest.raises(ValueError, match="not a valid"):
        validate_mnemonic(" ".join(["abandon"] * 12))
    with pytest.raises(ValueError, match="not a valid"):
        base_config("node1", "not a mnemonic " * 4)


def test_the_postgres_init_script_creates_one_database_per_node() -> None:
    sql = postgres_init_sql()
    assert sql.splitlines() == [f"CREATE DATABASE {n};" for n in NODES]


def test_the_base_config_serves_the_paladin_ui_under_the_http_rpc_server() -> None:
    """The image ships the UI in /app/ui; it is only served when `staticServers` enables it."""
    text = base_config("node1", PHRASE)
    http_block = text.split("rpcServer:\n", 1)[1].split("  ws:\n", 1)[0]
    assert "    staticServers:\n" in http_block
    expected = (
        "      - enabled: true\n",
        "        staticPath: /app/ui\n",
        "        urlPath: /ui\n",
        "        baseRedirect: /ui/\n",
    )
    for line in expected:
        assert line in http_block


def test_the_ui_is_on_the_same_published_port_as_the_rpc_server() -> None:
    from src.core.paladin.config import UI_PATH

    assert UI_PATH == "/ui"
    assert RPC_HTTP_PORT == 8548  # http://localhost:8548/ui/ on node1, 8648 and 8748 on the others


def test_the_committed_node_configs_are_what_the_builder_makes_from_their_own_seed() -> None:
    """`init` regenerates these files with new seeds, so they are patched in place when the builder
    changes; this keeps them in step with it (the seed is the only part that is not derived)."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "network-config" / "paladin"
    for node in NODES:
        committed = (root / node / "pldconf.paladin.yaml").read_text(encoding="utf-8")
        seed = re.search(r'inline: "([a-z ]+)"', committed)
        assert seed is not None, node
        assert committed == base_config(node, seed.group(1)), node
