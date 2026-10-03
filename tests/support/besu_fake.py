"""A stand-in for `besu operator generate-blockchain-config`, so unit tests need no Docker."""

import json
from collections.abc import Callable
from pathlib import Path

Generator = Callable[[Path, Path], None]


def fake_generator(
    seed: int = 1,
    count: int = 1,
    omit_from_extra_data: bool = False,
    asked_for: int | None = None,
) -> Generator:
    """Write what `besu operator generate-blockchain-config` writes, with made-up keys.

    It makes `count` validators and checks that this is what it was asked for (`asked_for`
    defaults to `count`; a test can set it differently to model a tool that misbehaves).
    """

    def run(config_file: Path, out_dir: Path) -> None:
        requested = json.loads(config_file.read_text(encoding="utf-8"))["blockchain"]["nodes"]
        assert requested["count"] == (count if asked_for is None else asked_for)
        assert requested["generate"] is True
        addresses = [f"0x{seed:02x}{i:02x}".ljust(42, "0") for i in range(count, 0, -1)]
        out_dir.mkdir(parents=True)
        listed = addresses[:-1] if omit_from_extra_data else addresses
        extra = "0x" + "00" * 32 + "".join(a.removeprefix("0x") for a in listed)
        genesis = {"config": {"chainId": 20260916, "qbft": {}}, "extraData": extra}
        (out_dir / "genesis.json").write_text(json.dumps(genesis), encoding="utf-8")
        for number, address in enumerate(addresses):
            folder = out_dir / "keys" / address
            folder.mkdir(parents=True)
            (folder / "key").write_text("0x" + f"{seed}{number}".zfill(64), encoding="utf-8")
            (folder / "key.pub").write_text("0x" + f"{seed}{number}".zfill(128), encoding="utf-8")

    return run


def fake_cert_maker() -> Callable[[str, Path], None]:
    """A stand-in for the certificate step (openssl in the Paladin image), no Docker needed."""

    def make(node: str, out_dir: Path) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, label in (("tls.crt", "CERT"), ("tls.key", "KEY"), ("ca.crt", "CERT")):
            text = f"{label} for {node}\n"
            (out_dir / name).write_text(text, encoding="utf-8", newline="\n")

    return make
