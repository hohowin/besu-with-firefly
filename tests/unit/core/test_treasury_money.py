import ast
from pathlib import Path

import pytest

from src.core.treasury.errors import InvalidAmount
from src.core.treasury.money import MAX_AMOUNT_MINOR, format_amount, parse_amount


@pytest.mark.parametrize(
    ("text", "minor"),
    [("1000.00", 100000), ("0.01", 1), ("1000", 100000), ("5.5", 550), ("0.10", 10)],
)
def test_parse_amount_valid(text: str, minor: int) -> None:
    assert parse_amount(text) == minor


@pytest.mark.parametrize(
    "text",
    ["0", "0.00", "-1", "+1", "1000.001", "1,000", "1e3", "", " ", "abc", ".5", "5.", "1 000"],
)
def test_parse_amount_invalid(text: str) -> None:
    with pytest.raises(InvalidAmount):
        parse_amount(text)


def test_parse_amount_cap() -> None:
    assert parse_amount("1000000.00") == MAX_AMOUNT_MINOR
    with pytest.raises(InvalidAmount, match="cap"):
        parse_amount("1000000.01")


def test_parse_amount_custom_cap() -> None:
    with pytest.raises(InvalidAmount):
        parse_amount("10.01", max_minor=1000)


def test_parse_amount_strips_surrounding_space() -> None:
    assert parse_amount(" 12.30 ") == 1230


@pytest.mark.parametrize(("minor", "text"), [(100000, "1000.00"), (1, "0.01"), (58000, "580.00")])
def test_format_amount(minor: int, text: str) -> None:
    assert format_amount(minor) == text


def test_format_rejects_negative() -> None:
    with pytest.raises(ValueError, match="negative"):
        format_amount(-1)


def _timeout_nodes(tree: ast.AST) -> set[ast.AST]:
    """The annotation and default of every `timeout` parameter: seconds, not money."""
    allowed: set[ast.AST] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        positional = node.args.args
        defaults = [None] * (len(positional) - len(node.args.defaults)) + list(node.args.defaults)
        for arg, default in zip(positional, defaults, strict=True):
            if arg.arg == "timeout":
                allowed.update(n for n in (arg.annotation, default) if n is not None)
    return allowed


def test_treasury_core_uses_no_floating_point() -> None:
    """TR-NFR-01: money is integers end to end. Only a `timeout` in seconds may be a float."""
    package = Path(__file__).resolve().parents[3] / "src" / "core" / "treasury"
    problems: list[str] = []
    for path in package.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        allowed = _timeout_nodes(tree)
        for node in ast.walk(tree):
            if node in allowed:
                continue
            if isinstance(node, ast.Name) and node.id == "float":
                problems.append(f"{path.name}:{node.lineno}")
            if isinstance(node, ast.Constant) and isinstance(node.value, float):
                problems.append(f"{path.name}:{node.lineno}")
    assert problems == []
