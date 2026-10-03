"""Build the input for `besu operator generate-blockchain-config` (pure, no I/O)."""

from typing import Any

MIN_VALIDATORS = 1  # one validator is a valid QBFT network; it just tolerates no failure (f = 0)


def build_qbft_config(
    validator_count: int,
    chain_id: int = 20260916,
    block_period_seconds: int = 2,
    request_timeout_seconds: int = 4,
    epoch_length: int = 30000,
) -> dict[str, Any]:
    """Return the QBFT genesis config for a zero-gas chain at the London and Shanghai forks.

    The shape matches the Phase 0 spike input. Every call returns a new, independent dict.
    """
    if validator_count < MIN_VALIDATORS:
        raise ValueError(
            f"QBFT needs at least {MIN_VALIDATORS} validator, got {validator_count}"
        )
    for name, value in (
        ("chain_id", chain_id),
        ("block_period_seconds", block_period_seconds),
        ("request_timeout_seconds", request_timeout_seconds),
        ("epoch_length", epoch_length),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be a positive integer, got {value}")

    return {
        "genesis": {
            "config": {
                "chainId": chain_id,
                "berlinBlock": 0,
                "londonBlock": 0,
                "zeroBaseFee": True,
                "shanghaiTime": 0,
                "qbft": {
                    "blockperiodseconds": block_period_seconds,
                    "epochlength": epoch_length,
                    "requesttimeoutseconds": request_timeout_seconds,
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
        "blockchain": {"nodes": {"generate": True, "count": validator_count}},
    }
