import pytest

from src.core.network.genesis import build_qbft_config

# Same content as the Phase 0 spike input (spike/qbft/qbft-config.json), with 4 validators.
EXPECTED_DEFAULT = {
    "genesis": {
        "config": {
            "chainId": 20260916,
            "berlinBlock": 0,
            "londonBlock": 0,
            "zeroBaseFee": True,
            "shanghaiTime": 0,
            "qbft": {
                "blockperiodseconds": 2,
                "epochlength": 30000,
                "requesttimeoutseconds": 4,
            },
        },
        "nonce": "0x0",
        "timestamp": "0x58ee40ba",
        "gasLimit": "0x1fffffffffffff",
        "difficulty": "0x1",
        "mixHash": "0x63746963616c2062797a616e74696e65206661756c7420746f6c6572616e6365",
        "coinbase": "0x0000000000000000000000000000000000000000",
        "alloc": {},
    },
    "blockchain": {"nodes": {"generate": True, "count": 4}},
}


def test_defaults_match_the_spike_input_with_four_validators() -> None:
    assert build_qbft_config(validator_count=4) == EXPECTED_DEFAULT


def test_parameters_are_applied() -> None:
    config = build_qbft_config(
        validator_count=7, chain_id=1337, block_period_seconds=5, request_timeout_seconds=10
    )
    assert config["genesis"]["config"]["chainId"] == 1337
    assert config["genesis"]["config"]["qbft"]["blockperiodseconds"] == 5
    assert config["genesis"]["config"]["qbft"]["requesttimeoutseconds"] == 10
    assert config["blockchain"]["nodes"]["count"] == 7


@pytest.mark.parametrize("count", [0, 1, 3])
def test_fewer_than_four_validators_is_rejected_and_names_the_rule(count: int) -> None:
    with pytest.raises(ValueError, match=r"n = 3f \+ 1"):
        build_qbft_config(validator_count=count)


@pytest.mark.parametrize(
    "kwargs",
    [{"chain_id": 0}, {"block_period_seconds": 0}, {"request_timeout_seconds": 0}],
)
def test_non_positive_values_are_rejected(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError, match="positive"):
        build_qbft_config(validator_count=4, **kwargs)


def test_each_call_returns_an_independent_dict() -> None:
    first = build_qbft_config(validator_count=4)
    first["genesis"]["alloc"]["0xabc"] = {"balance": "0x1"}
    assert build_qbft_config(validator_count=4)["genesis"]["alloc"] == {}
