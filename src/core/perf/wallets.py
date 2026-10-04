"""The benchmark wallets (pure): one per Caliper worker, derived from a demo seed.

Caliper's Ethereum connector gives worker `i` the key at `m/44'/60'/i'/0/0` of
`EthereumHDKey.fromMasterSeed(seed)`, so deriving the same keys here means the chain-layer round
(Caliper signs) and the FireFly-layer round (FireFly's signer signs) use the same wallets. The seed
is public and the keys are demo only (plan D-10).
"""

import hashlib
import hmac

from eth_keys.datatypes import PrivateKey

from src.core.network.wallets import Wallet

PERF_SEED = "besu-with-firefly perf demo seed"
MAX_WALLETS = 999  # names are `perf-001` to `perf-999`

_HARDENED = 0x80000000
_ORDER = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141  # secp256k1 group order


def derive_wallets(count: int, seed: str = PERF_SEED) -> list[Wallet]:
    """The first `count` wallets for `seed`: `perf-001` is worker 0, `perf-002` is worker 1."""
    if not 1 <= count <= MAX_WALLETS:
        raise ValueError(f"the number of wallets must be between 1 and {MAX_WALLETS}, got {count}")
    master = _master_key(seed.encode("utf-8"))
    wallets = []
    for worker in range(count):
        key, chain = master
        for index in (44 + _HARDENED, 60 + _HARDENED, worker + _HARDENED, 0, 0):
            key, chain = _child_key(key, chain, index)
        private = PrivateKey(key.to_bytes(32, "big"))
        wallets.append(
            Wallet(
                name=f"perf-{worker + 1:03d}",
                address=str(private.public_key.to_checksum_address()).lower(),
                private_key="0x" + private.to_hex().removeprefix("0x"),
            )
        )
    return wallets


def benchmark_wallets(workers: int, seed: str = PERF_SEED) -> list[Wallet]:
    """The wallets for a benchmark with `workers` workers: twice as many, one set per layer.

    The first `workers` wallets are for the chain layer, the next `workers` for the FireFly layer.
    FireFly's evmconnect works out a key's next nonce from its own records, so it falls behind a key
    that was also sent from directly; the layers must never share a wallet.
    """
    return derive_wallets(2 * workers, seed)


def _master_key(seed: bytes) -> tuple[int, bytes]:
    digest = hmac.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
    return int.from_bytes(digest[:32], "big"), digest[32:]


def _child_key(key: int, chain: bytes, index: int) -> tuple[int, bytes]:
    """BIP32 private child derivation."""
    if index >= _HARDENED:
        data = b"\x00" + key.to_bytes(32, "big")
    else:
        data = PrivateKey(key.to_bytes(32, "big")).public_key.to_compressed_bytes()
    digest = hmac.new(chain, data + index.to_bytes(4, "big"), hashlib.sha512).digest()
    left = int.from_bytes(digest[:32], "big")
    child = (left + key) % _ORDER
    if left >= _ORDER or child == 0:
        raise ValueError(f"index {index} gives an invalid key; use another seed")
    return child, digest[32:]
