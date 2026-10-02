from src.core.network.besu_logs import latest_block_number, peer_count

# Lines copied from a real Besu 26.8.1 QBFT validator (ANSI colours already stripped).
IMPORTED = (
    "2026-10-02 14:00:24.250+0000 | BftProcessorExecutor-QBFT-0 | INFO  | QbftBesuControllerBuilder"
    " | Imported empty block #1 / 0 tx / 0 pending / 0 (0.0%) gas / (0xbf3dd6c71fd4)"
)
PRODUCED = (
    "2026-10-02 14:00:30.040+0000 | BftProcessorExecutor-QBFT-0 | INFO  | QbftBesuControllerBuilder"
    " | Produced #4  (11bcc.....571c8)|    0 tx | 0 pending | 0 (0.0%) gas in 0.037s"
)
IMPORTED_WITH_TX = (
    "2026-10-02 14:01:00.000+0000 | BftProcessorExecutor-QBFT-0 | INFO  | QbftBesuControllerBuilder"
    " | Imported #1,234 / 3 tx / 0 pending / 21000 (0.0%) gas / (0xabc)"
)
PEERS_0 = (
    "2026-10-02 14:00:19.977+0000 | main | INFO  | FullSyncTargetManager | Unable to find sync"
    " target. Waiting for 5 peers minimum. Currently checking 0 peers for usefulness"
)
PEERS_3 = PEERS_0.replace("checking 0 peers", "checking 3 peers")


def test_latest_block_reads_both_produced_and_imported_lines() -> None:
    assert latest_block_number(IMPORTED) == 1
    assert latest_block_number(PRODUCED) == 4


def test_latest_block_handles_thousands_separators() -> None:
    assert latest_block_number(IMPORTED_WITH_TX) == 1234


def test_latest_block_takes_the_highest_number_in_the_log() -> None:
    assert latest_block_number("\n".join([PRODUCED, IMPORTED, IMPORTED_WITH_TX])) == 1234


def test_latest_block_is_none_when_no_block_line_exists() -> None:
    assert latest_block_number(PEERS_3) is None
    assert latest_block_number("") is None


def test_peer_count_is_the_last_reported_value() -> None:
    assert peer_count("\n".join([PEERS_0, PEERS_3])) == 3
    assert peer_count("\n".join([PEERS_3, PEERS_0])) == 0


def test_peer_count_is_none_when_never_reported() -> None:
    assert peer_count(IMPORTED) is None
