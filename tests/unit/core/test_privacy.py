"""Who may see which Noto coin, and what must not appear on the public chain."""

from typing import Any

from src.core.paladin.privacy import coin_amounts, find_leaks, visibility_problems


def state(amount: str | None, **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"owner": "0x" + "11" * 20, "salt": "0x" + "22" * 32}
    if amount is not None:
        data["amount"] = amount
    return {"id": "0x01", "data": data, **extra}


def word(value: int) -> str:
    return f"{value:064x}"


def test_coin_amounts_lists_the_coins_sorted_and_ignores_other_states() -> None:
    states = [state("60"), state(None), state("40", spent={"transaction": "t"})]
    assert coin_amounts(states) == [40, 60]


def test_coin_amounts_of_nothing_is_empty() -> None:
    assert coin_amounts([]) == []


def test_matching_visibility_has_no_problems() -> None:
    seen = {"node1": [40, 60, 100], "node2": [40, 60, 100], "node3": [40]}
    assert visibility_problems(seen, seen) == []


def test_a_non_party_that_sees_a_coin_is_reported_as_a_leak() -> None:
    seen = {"node1": [100], "node2": [100], "node3": [100]}
    expected = {"node1": [100], "node2": [100], "node3": []}
    problems = visibility_problems(seen, expected)
    assert len(problems) == 1
    assert "node3" in problems[0]
    assert "leak" in problems[0]


def test_a_party_that_misses_its_coin_is_reported() -> None:
    problems = visibility_problems({"node3": []}, {"node3": [40]})
    assert len(problems) == 1
    assert "node3" in problems[0]
    assert "missing" in problems[0]


def test_logs_without_amounts_or_addresses_are_clean() -> None:
    logs = [{"data": "0x" + word(7) + word(12345), "topics": ["0x" + "ab" * 32]}]
    assert find_leaks(logs, amounts=[100, 40, 60], addresses=["0x" + "11" * 20]) == []


def test_an_amount_in_the_data_is_a_leak() -> None:
    logs = [{"data": "0x" + word(1) + word(40), "topics": []}]
    leaks = find_leaks(logs, amounts=[100, 40, 60], addresses=[])
    assert len(leaks) == 1
    assert "40" in leaks[0]


def test_an_amount_in_a_topic_is_a_leak() -> None:
    logs = [{"data": "0x", "topics": ["0x" + word(100)]}]
    assert find_leaks(logs, amounts=[100], addresses=[])


def test_an_address_padded_in_a_word_is_a_leak() -> None:
    address = "0x" + "ab" * 20
    logs = [{"data": "0x" + "00" * 12 + "ab" * 20, "topics": []}]
    leaks = find_leaks(logs, amounts=[], addresses=[address])
    assert len(leaks) == 1
    assert address in leaks[0]


def test_address_matching_ignores_case() -> None:
    logs = [{"data": "0x" + "00" * 12 + "ab" * 20, "topics": []}]
    assert find_leaks(logs, amounts=[], addresses=["0x" + "AB" * 20])
