"""Read facts out of Besu validator logs (pure text parsing, no I/O).

Validators publish no RPC, so block height and peers come from their logs.
"""

import re

# "Produced #4 ..." on the proposer, "Imported empty block #5 ..." or "Imported #1,234 ..."
# on the other validators.
_BLOCK = re.compile(r"(?:Produced|Imported(?: empty block)?)\s+#([\d,]+)")
# "Currently checking 3 peers" while waiting for a sync target (start-up), then
# "... in 0.000s. Peers: 5" on every block a synced node imports.
_PEERS = re.compile(r"Currently checking (\d+) peers|\bPeers: (\d+)")


def latest_block_number(log_text: str) -> int | None:
    """Highest block number mentioned by a Produced or Imported line, or None."""
    numbers = [int(match.replace(",", "")) for match in _BLOCK.findall(log_text)]
    return max(numbers) if numbers else None


def peer_count(log_text: str) -> int | None:
    """The most recently reported peer count, or None if Besu never reported one."""
    counts = [int(checking or synced) for checking, synced in _PEERS.findall(log_text)]
    return counts[-1] if counts else None
