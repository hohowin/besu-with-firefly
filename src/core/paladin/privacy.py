"""Noto privacy checks (pure, no I/O).

Noto keeps each coin as a private state that only the parties to it receive. The chain only
carries opaque hashes. These functions compare what each node lists with what it should see, and
look through public logs for amounts or party addresses.
"""

from collections.abc import Mapping, Sequence
from typing import Any

WORD_HEX = 64  # a 32-byte word in hex


def coin_amounts(states: Sequence[Mapping[str, Any]]) -> list[int]:
    """The amounts of the coins among `states`, sorted. Spent coins count: they were seen."""
    amounts = [
        int(str(state["data"]["amount"]), 0)
        for state in states
        if "amount" in state.get("data", {})
    ]
    return sorted(amounts)


def visibility_problems(
    seen: Mapping[str, Sequence[int]], expected: Mapping[str, Sequence[int]]
) -> list[str]:
    """Differences between the coin amounts each node saw and the amounts it should see."""
    problems: list[str] = []
    for node in sorted(expected):
        got = sorted(seen.get(node, []))
        want = sorted(expected[node])
        extra = [a for a in got if a not in want]
        missing = [a for a in want if a not in got]
        if extra:
            problems.append(f"{node}: leak, sees {extra} but should see {want}")
        if missing:
            problems.append(f"{node}: missing {missing}, sees {got}")
    return problems


def _words(log: Mapping[str, Any]) -> list[str]:
    """Every 32-byte word of a log's data and topics, lower case hex without `0x`."""
    data = str(log.get("data", "0x")).removeprefix("0x").lower()
    words = [data[i : i + WORD_HEX] for i in range(0, len(data), WORD_HEX)]
    words += [str(topic).removeprefix("0x").lower() for topic in log.get("topics", [])]
    return words


def find_leaks(
    logs: Sequence[Mapping[str, Any]], amounts: Sequence[int], addresses: Sequence[str]
) -> list[str]:
    """Where an amount (as a whole word) or an address (inside a word) shows in public logs."""
    leaks: list[str] = []
    for index, log in enumerate(logs):
        words = _words(log)
        for amount in amounts:
            if f"{amount:0{WORD_HEX}x}" in words:
                leaks.append(f"log {index} carries the amount {amount}")
        for address in addresses:
            needle = address.removeprefix("0x").lower()
            if any(needle in word for word in words):
                leaks.append(f"log {index} carries the address {address}")
    return leaks
