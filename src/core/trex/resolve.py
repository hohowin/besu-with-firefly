"""Turn plan arguments into the values sent to FireFly (pure)."""

from collections.abc import Mapping, Sequence
from typing import Any

from src.core.trex.plan import Account, Ref


def resolve_value(value: Any, contracts: Mapping[str, str], accounts: Mapping[str, str]) -> Any:
    """Replace `Ref` and `Account` with addresses, also inside lists and structs (dicts).

    Raises KeyError naming the reference that has no address.
    """
    if isinstance(value, Ref):
        return contracts[value.name]
    if isinstance(value, Account):
        return accounts[value.name]
    if isinstance(value, dict):
        return {key: resolve_value(item, contracts, accounts) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [resolve_value(item, contracts, accounts) for item in value]
    return value


def resolve_args(
    args: Sequence[Any], contracts: Mapping[str, str], accounts: Mapping[str, str]
) -> list[Any]:
    return [resolve_value(arg, contracts, accounts) for arg in args]


def call_input(abi_inputs: Sequence[Mapping[str, Any]], args: Sequence[Any]) -> dict[str, Any]:
    """FireFly takes the arguments of a call by parameter name, so pair them with the ABI's."""
    if len(abi_inputs) != len(args):
        raise ValueError(f"the method takes {len(abi_inputs)} arguments, got {len(args)}")
    names = [str(item.get("name", "")) for item in abi_inputs]
    if not all(names):
        raise ValueError("a parameter has no name in the ABI, so it cannot be passed by name")
    return dict(zip(names, args, strict=True))
