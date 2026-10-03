"""Private Noto token operations through the Paladin nodes (adapter)."""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from src.core.paladin.bootstrap import DEPLOY_NODE
from src.core.paladin.noto import (
    balance_call,
    balance_from,
    deploy_request,
    mint_request,
    transfer_request,
)


class NotoNode(Protocol):
    def send_and_wait(self, node: str, transaction: Mapping[str, Any]) -> dict[str, Any]: ...

    def private_call(self, node: str, call: Mapping[str, Any]) -> Any: ...


def deploy_token(client: NotoNode) -> str:
    """Deploy a new Noto token through node1 (the notary's node) and return its address."""
    receipt = client.send_and_wait(DEPLOY_NODE, deploy_request())
    address = str(receipt.get("contractAddress", ""))
    if not address:
        raise RuntimeError(f"Noto deploy receipt has no contractAddress: {receipt}")
    return address


def mint(
    client: NotoNode, token: str, abi: Sequence[Mapping[str, Any]], to: str, amount: int
) -> dict[str, Any]:
    """Mint to `to`. The notary signs, so it is submitted on node1."""
    return client.send_and_wait(DEPLOY_NODE, mint_request(token, abi, to, amount))


def transfer(
    client: NotoNode,
    token: str,
    abi: Sequence[Mapping[str, Any]],
    sender: str,
    to: str,
    amount: int,
) -> dict[str, Any]:
    """Transfer from `sender`, submitted on the sender's own node (`name@node`)."""
    node = sender.split("@", 1)[1]
    return client.send_and_wait(node, transfer_request(token, abi, sender, to, amount))


def balance_of(client: NotoNode, token: str, abi: Sequence[Mapping[str, Any]], account: str) -> int:
    """The balance of `account`, asked of the account's own node (`name@node`)."""
    node = account.split("@", 1)[1]
    return balance_from(client.private_call(node, balance_call(token, abi, account)))
