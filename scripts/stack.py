"""Entry point: `python scripts/stack.py <command>`. The logic is in src/adapters/stack_cli.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.adapters.stack_cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
