"""`init` against the real Besu image (needs Docker and hyperledger/besu:26.8.1)."""

import json
from pathlib import Path

import pytest

from src.adapters.besu_config import AlreadyInitialisedError, docker_generator, init_network
from src.core.network.validators import extra_data_lists_all


@pytest.mark.integration
def test_init_with_the_real_besu_tool(tmp_path: Path) -> None:
    result = init_network(tmp_path, generator=docker_generator())

    genesis = json.loads((tmp_path / "genesis.json").read_text(encoding="utf-8"))
    assert "qbft" in genesis["config"]
    assert genesis["config"]["chainId"] == 20260916
    assert genesis["config"]["zeroBaseFee"] is True
    assert len(result.validator_addresses) == 4
    assert extra_data_lists_all(genesis["extraData"], result.validator_addresses)

    nodes = json.loads((tmp_path / "static-nodes.json").read_text(encoding="utf-8"))
    assert len(nodes) == 4
    for number, enode in enumerate(nodes, start=1):
        pub = (tmp_path / "validator-keys" / f"validator-{number}" / "key.pub").read_text("utf-8")
        assert enode.startswith("enode://" + pub.strip().removeprefix("0x") + "@172.28.0.")

    document = json.loads((tmp_path / "wallets.json").read_text(encoding="utf-8"))
    firefly = tmp_path / "firefly"
    assert len(list((firefly / "signer-data" / "keystore").glob("*.toml"))) == len(
        document["wallets"]
    )
    admin = next(w for w in document["wallets"] if w["name"] == "admin")
    assert admin["address"] in (firefly / "core.yml").read_text(encoding="utf-8")

    first_keys = (tmp_path / "validator-keys" / "validator-1" / "key").read_bytes()
    with pytest.raises(AlreadyInitialisedError):
        init_network(tmp_path, generator=docker_generator())
    assert (tmp_path / "validator-keys" / "validator-1" / "key").read_bytes() == first_keys

    init_network(tmp_path, generator=docker_generator(), force=True)
    assert (tmp_path / "validator-keys" / "validator-1" / "key").read_bytes() != first_keys
