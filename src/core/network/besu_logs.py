"""Read facts out of Besu validator logs (pure text parsing, no I/O).

Validators publish no RPC, so their block height comes from their logs.
"""

import re

# "Produced #4 ..." on the proposer, "Imported empty block #5 ..." or "Imported #1,234 ..."
# on the other validators.
_BLOCK = re.compile(r"(?:Produced|Imported(?: empty block)?)\s+#([\d,]+)")


def latest_block_number(log_text: str) -> int | None:
    """Highest block number mentioned by a Produced or Imported line, or None."""
    numbers = [int(match.replace(",", "")) for match in _BLOCK.findall(log_text)]
    return max(numbers) if numbers else None
