import pytest

from src.core.trex.plan import Account, Ref
from src.core.trex.resolve import call_input, resolve_args, resolve_value

CONTRACTS = {"factory": "0x" + "11" * 20}
ACCOUNTS = {"admin": "0x" + "aa" * 20}


def test_refs_and_accounts_become_addresses() -> None:
    assert resolve_value(Ref("factory"), CONTRACTS, ACCOUNTS) == CONTRACTS["factory"]
    assert resolve_value(Account("admin"), CONTRACTS, ACCOUNTS) == ACCOUNTS["admin"]


def test_plain_values_are_kept() -> None:
    assert resolve_value(True, CONTRACTS, ACCOUNTS) is True
    assert resolve_value(7, CONTRACTS, ACCOUNTS) == 7
    assert resolve_value("0x00", CONTRACTS, ACCOUNTS) == "0x00"


def test_structs_and_lists_are_resolved_inside() -> None:
    value = ({"a": Ref("factory"), "b": [Account("admin"), 3]}, [Ref("factory")])
    assert resolve_args(value, CONTRACTS, ACCOUNTS) == [
        {"a": CONTRACTS["factory"], "b": [ACCOUNTS["admin"], 3]},
        [CONTRACTS["factory"]],
    ]


def test_an_unresolved_reference_is_a_clear_error() -> None:
    with pytest.raises(KeyError, match="ghost"):
        resolve_value(Ref("ghost"), CONTRACTS, ACCOUNTS)
    with pytest.raises(KeyError, match="bob"):
        resolve_value(Account("bob"), CONTRACTS, ACCOUNTS)


def test_call_input_maps_positional_arguments_to_the_parameter_names() -> None:
    inputs = [{"name": "_version", "type": "tuple"}, {"name": "_trex", "type": "tuple"}]
    expected = {"_version": {"major": 4}, "_trex": {"x": 1}}
    assert call_input(inputs, [{"major": 4}, {"x": 1}]) == expected


def test_call_input_rejects_a_wrong_number_of_arguments() -> None:
    with pytest.raises(ValueError, match="takes 2 arguments, got 1"):
        call_input([{"name": "a"}, {"name": "b"}], [1])


def test_call_input_rejects_an_unnamed_parameter() -> None:
    with pytest.raises(ValueError, match="no name"):
        call_input([{"name": ""}], [1])
