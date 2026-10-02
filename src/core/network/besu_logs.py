"""Read facts out of Besu validator logs (pure text parsing, no I/O).

Validators publish no RPC, so block height and peers come from their logs.
"""

import re

# "Produced #4 ..." on the proposer, "Imported empty block #5 ..." or "Imported #1,234 ..."
# on the other validators.
_BLOCK = re.compile(r"(?:Produced|Imported(?: empty block)?)\s+#([\d,]+)")
_PEERS = re.compile(r"Currently checking (\d+) peers")


def latest_block_number(log_text: str) -> int | None:
    """Highest block number mentioned by a Produced or Imported line, or None."""
    numbers = [int(match.replace(",", "")) for match in _BLOCK.findall(log_text)]
    return max(numbers) if numbers else None


def peer_count(log_text: str) -> int | None:
    """The most recently reported peer count, or None if Besu never reported one."""
    counts = _PEERS.findall(log_text)
    return int(counts[-1]) if counts else None
