"""Command-line inputs for a contract call (pure): `NAME=VALUE` pairs and wallet names.

Values stay text; FireFly converts them with the contract's ABI. A value written `@anson` is the
address of the wallet `anson`. The contract and FireFly check every value again, so this only
refuses what is clearly a typo before anything is sent.
"""

import re
from collections.abc import Mapping, Sequence

_HEX = re.compile(r"0x(?:[0-9a-fA-F]{2})+")


class InputError(ValueError):
    """An input the command line cannot turn into a call."""


def resolve_identity(name: str, wallets: Mapping[str, str]) -> str:
    """The address of the wallet called `name`."""
    try:
        return wallets[name]
    except KeyError:
        raise InputError(f"no wallet called {name!r} (known: {', '.join(wallets)})") from None


def parse_inputs(pairs: Sequence[str], wallets: Mapping[str, str]) -> dict[str, str]:
    inputs: dict[str, str] = {}
    for pair in pairs:
        name, separator, value = pair.partition("=")
        name = name.strip()
        if not separator or not name:
            raise InputError(f"input {pair!r} is not NAME=VALUE")
        if name in inputs:
            raise InputError(f"input {name!r} is given twice")
        inputs[name] = _value(name, value, wallets)
    return inputs


def _value(name: str, value: str, wallets: Mapping[str, str]) -> str:
    if value.startswith("@"):
        return resolve_identity(value[1:], wallets)
    if value.lower().startswith("0x") and not _HEX.fullmatch(value):
        raise InputError(f"input {name!r}: {value!r} is not valid hex (whole bytes, 0x then pairs)")
    return value
