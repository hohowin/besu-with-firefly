# Performance results: chain layer vs FireFly layer

Measured 2026-10-04 with Caliper 0.6.0 on the stack in this repository. **These numbers describe this demo configuration (one validator, 2 s blocks, ten containers on one laptop). They are not Besu's limits and not FireFly's limits.**

## What was measured

The same `COIN.transfer(to, 0.001 COIN)` (an ERC-3643 token: the transfer checks the recipient's identity, so it is more work than a plain value transfer), sent two ways:

- **Chain layer**: Caliper signs and sends straight to `besu-rpc-anson` over JSON-RPC (`ws://localhost:8546`) and waits for one confirmation block.
- **FireFly layer**: a custom Caliper connector calls FireFly's contract API, `POST /apis/coin/invoke/transfer?confirm=true`, signing with FireFly's signer, and waits for FireFly to report the operation `Succeeded`. A transaction counts only then.

Both layers used 10 workers, each sending from its own wallet to the next wallet of its set (every recipient a verified investor). The layers use different wallets (see [perf/README.md](../perf/README.md) for why).

## Configuration

Copied from the saved snapshots in [perf-data/](perf-data/); the two layers' snapshots are identical except for the layer and the time.

| Setting | Value |
|---|---|
| Workers (and wallets per layer) | 10 |
| Offered load | 5 TPS in all (0.5 per worker), fixed rate |
| Transactions per round | 300 (30 per worker), about 60 s |
| Amount | 1000000000000000 base units (0.001 COIN) |
| Block period (genesis, QBFT) | 2 s |
| Gas limit (genesis) | `0x1fffffffffffff` (9007199254740991) |
| Gas price | 0 (`--min-gas-price=0`) |
| Validators / RPC nodes | 1 / 1 |
| Besu | `hyperledger/besu:26.8.1` |
| FireFly core | `sha256:d321bcd8c567…` (see `docker-compose.yml`) |
| Caliper | 0.6.0 (`web3@1.3.0`), local workers |
| Host | Windows 11, Docker Desktop (engine 29.5.2), 12 CPUs and 15.5 GiB for Docker, Node v24.11.1 |

## Results

Two runs, each from `python scripts/stack.py reset && up && deploy`, then `perf-setup --wallets 10 --coins 100`, then the chain round, then the FireFly round. Every transaction of all four rounds succeeded (300 of 300), and the sum of the wallets' balances was the same before and after each round.

| Run | Layer | Succeeded | Throughput (TPS) | Avg latency (s) | Min latency (s) | Max latency (s) |
|---|---|---|---|---|---|---|
| 1 | Chain | 300 / 300 | 5.1 | 0.99 | 0.89 | 1.19 |
| 1 | FireFly | 300 / 300 | 4.8 | 4.92 | 2.74 | 8.59 |
| 2 | Chain | 300 / 300 | 5.1 | 0.74 | 0.63 | 1.06 |
| 2 | FireFly | 300 / 300 | 4.9 | 4.63 | 2.74 | 8.59 |

**Difference (FireFly minus chain, same offered load):**

| Run | Average latency | Throughput |
|---|---|---|
| 1 | +3.93 s (about 5 times the chain layer) | -0.3 TPS (4.8 against 5.1) |
| 2 | +3.89 s (about 6 times the chain layer) | -0.2 TPS (4.9 against 5.1) |

At 5 TPS offered, both layers keep up (throughput is within a few percent of the offered rate), so the visible cost of going through FireFly here is latency: roughly four extra seconds per transfer. This note does not break that down into its causes (FireFly's own handling, evmconnect's submission and its wait for confirmation, the signer); nothing was measured to split it.

Setup (making 20 wallets verified investors holding 100 COIN each, through FireFly) took 211.9 s in run 1 and 161.6 s in run 2, so it takes longer than the two rounds together.

Raw data: `perf-data/run{1,2}-{chain,firefly}.json` (Caliper's summary row and the snapshot). The FireFly maximum and minimum latency are identical in the two runs (8.59 s and 2.74 s); they are Caliper's own figures as printed, and one run each is too few to say whether that is chance or something in the pipeline's timing.

## What these numbers do and do not say

- They are two runs of one configuration, not a distribution. During development the same configuration gave a FireFly average latency of 3.17 s to 3.21 s on a stack that had been up for longer, and a chain average of 0.41 s to 1.86 s over several runs, so expect a spread of this size from run to run.
- **The load is below FireFly's ceiling on purpose.** At 20 TPS offered (600 transactions, 10 workers, otherwise the same configuration) one run on a fresh stack gave, for the FireFly layer, 145 succeeded and 455 failed, 8 TPS and an average latency of 67.7 s; the failures were FireFly's submissions to evmconnect timing out and the 100 s `confirm=true` limit. The chain layer took the same 20 TPS (19 TPS, average 1.86 s). That was one run and is not repeated here; it says the FireFly layer in this setup saturates at roughly 8 TPS, with the 2 s block period and the single FireFly and evmconnect pair.
- A 2 s block period puts a floor under every confirmed transaction's latency on both layers. A single validator, one RPC node, no other load and zero gas are all unlike a production network.
- Nothing here was tuned for throughput (plan: out of scope). Caliper 0.6.0 and `web3@1.3.0` are old and were used because 0.7.1 has no Ethereum connector.
- The benchmark wallets and the demo seed are public and for this demo only.

## Repeat it

```
python scripts/stack.py reset && python scripts/stack.py up && python scripts/stack.py deploy
python scripts/stack.py perf-setup --wallets 10 --coins 100
cd perf && npm ci && npm install --no-save web3@1.3.0
npm run round:chain
npm run round:firefly
```

Each round writes `perf/results/<layer>.json` (numbers and configuration) and `perf/results/<layer>-report.html`. `PERF_WALLETS`, `PERF_TPS`, `PERF_TXS` and `PERF_AMOUNT` change the load (see [perf/README.md](../perf/README.md)). Funding the wallets mints new COIN, so run `python scripts/stack.py reset` after benchmarking before running the integration tests.
