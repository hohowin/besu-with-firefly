"""Request builders for private Noto calls (pure, no I/O).

Noto is a Paladin domain: its calls are `type: private` transactions. The notary (here
`notary@node1`) mints; the owner of a coin transfers it. Deploying a token needs a constructor
ABI naming the notary, or Paladin fails with `PD200007: Parameter 'notary' is required`.
"""

from collections.abc import Mapping, Sequence
from typing import Any

DOMAIN = "noto"
NOTARY = "notary@node1"
NOTARY_MODE = "basic"

_CONSTRUCTOR = [
    {
        "type": "constructor",
        "inputs": [
            {"name": "notary", "type": "string"},
            {"name": "notaryMode", "type": "string"},
        ],
    }
]


def identity(name: str, node: str) -> str:
    """A Paladin identity locator, for example `anson@node2`."""
    return f"{name}@{node}"


def _positive(amount: int) -> int:
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")
    return amount


def deploy_request() -> dict[str, Any]:
    return {
        "type": "private",
        "domain": DOMAIN,
        "from": NOTARY,
        "abi": _CONSTRUCTOR,
        "data": {"notary": NOTARY, "notaryMode": NOTARY_MODE},
    }


def _call(
    token: str,
    abi: Sequence[Mapping[str, Any]],
    sender: str,
    function: str,
    data: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "type": "private",
        "domain": DOMAIN,
        "from": sender,
        "to": token,
        "abi": list(abi),
        "function": function,
        "data": dict(data),
    }


def mint_request(
    token: str, abi: Sequence[Mapping[str, Any]], to: str, amount: int
) -> dict[str, Any]:
    return _call(token, abi, NOTARY, "mint", {"to": to, "amount": _positive(amount), "data": "0x"})


def transfer_request(
    token: str, abi: Sequence[Mapping[str, Any]], sender: str, to: str, amount: int
) -> dict[str, Any]:
    return _call(
        token, abi, sender, "transfer", {"to": to, "amount": _positive(amount), "data": "0x"}
    )


def balance_call(token: str, abi: Sequence[Mapping[str, Any]], account: str) -> dict[str, Any]:
    return _call(token, abi, account, "balanceOf", {"account": account})


def balance_from(reply: Mapping[str, Any]) -> int:
    """The `totalBalance` of a `balanceOf` reply. An overflowing sum is not a balance."""
    if reply.get("overflow"):
        raise ValueError(f"balance overflow in reply {dict(reply)}")
    if "totalBalance" not in reply:
        raise ValueError(f"reply has no totalBalance: {dict(reply)}")
    return int(str(reply["totalBalance"]), 0)
