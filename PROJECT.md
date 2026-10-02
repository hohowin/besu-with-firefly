# PROJECT.md

> Architecture, conventions, and commands. Referenced by `CLAUDE.md` §0, §4, §5. Fill in the TODOs per project.

## Stack

- Language: Python
- Lint: `ruff` · Types: `mypy` · Tests: `pytest`
- Diagrams: Mermaid

## Layers

- `src/core/` — pure logic. No I/O, no side effects (no `print()`, `input()`, `plt.show()`).
- Adapters (CLI, API, MCP) — I/O, formatting, user interaction. Call into core only.
- Tests mirror the structure of the code they cover.
- API handlers are sync (`def`, not `async def`) when they wrap blocking calls.

## Commands

TODO: install, run, lint (`ruff check .`), type-check (`mypy .`), test (`pytest`).

## Directory Layout

TODO: fill in actual layout.
