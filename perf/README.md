# perf/ — Caliper benchmarks (Phase 5)

Measures a `COIN` `transfer` sent straight to Besu and sent through FireFly. Needs the stack up and deployed
(`python scripts/stack.py up && python scripts/stack.py deploy`) and `npm ci` in `contracts/`.

## Install

```
cd perf
npm ci
npm install --no-save web3@1.3.0
```

`web3@1.3.0` is installed by hand because `caliper bind` fails on Windows (`spawn EINVAL`); it is the only thing `bind`
would do. Caliper is pinned to exactly 0.6.0 (0.7.1 has no Ethereum connector). Its dependencies are old and
deprecated; that is accepted for a local demo.

## Commands

| Command | What it does |
|---|---|
| `npm run smoke` | A read-only `COIN.name()` round against the deployed token. Writes `report.html` (not committed). |
| `npm run prepare-run` | Writes `generated/` (token address and ABI, the Caliper network configs and the benchmark file) from `deployed-addresses.json`. Run by every round. |
| `npm run round:chain` | The chain-layer round: `COIN.transfer` sent from N wallets straight to Besu over JSON-RPC. Writes `results/chain.json` (numbers and configuration) and `results/chain-report.html`. Needs `python scripts/stack.py perf-setup` first. |
| `npm run round:firefly` | The same transfers through FireFly's contract API (`apis/coin/invoke/transfer?confirm=true`) with the custom connector in `connector/`. Writes `results/firefly.json` and `results/firefly-report.html`. A transaction counts only if FireFly reports the operation `Succeeded`. |
| `npm test` | Unit tests of the report parser and the snapshot (no stack needed). |
| `node lib/derive.js "<seed>" [count]` | Prints the wallets Caliper derives from a seed, one per worker. |

## The load

One place sets the load of both layers, as environment variables (defaults in `lib/params.js`):

| Variable | Default | Meaning |
|---|---|---|
| `PERF_WALLETS` | 10 | Wallets, and Caliper workers: worker `i` owns wallet `i` |
| `PERF_TPS` | 5 | Transactions per second offered in all |
| `PERF_TXS` | 300 | Transactions in all (a multiple of `PERF_WALLETS`) |
| `PERF_AMOUNT` | `1000000000000000` | Base units per transfer (0.001 COIN) |

Worker `i` sends to wallet `i+1` of its layer (the last one to the first), so every recipient is a verified investor.
Caliper takes `txNumber` and `tps` as totals and splits them across the workers. A round fails if a transaction fails,
or if the sum of the wallets' balances changed.

**Two sets of wallets.** `perf-setup --wallets N` prepares `2N` wallets: the first `N` are for the chain layer and the
next `N` for the FireFly layer. FireFly's evmconnect works out a key's next nonce from its own records, so a key that
the chain-layer round also sent from directly makes it fail with `Nonce too low`, and a restart does not clear it. With
separate sets the rounds can run in any order and be repeated.

**Why 5 TPS.** On this setup (one validator, 2 s blocks, one FireFly) the FireFly layer takes about 8 TPS before
evmconnect's submissions time out: at `PERF_TPS=20` with 600 transactions one run gave 145 succeeded and 455 failed with
an average latency of 67 s. A default round must succeed on both layers, so it offers a load both can take. Raise
`PERF_TPS` to see the FireFly ceiling; a round that fails exits non-zero and says why.

Before a round the runner waits until FireFly has no pending operations left from an earlier round.

## Notes

- The token is already deployed, so rounds run with `--caliper-flow-skip-install`, and the network config carries the
  contract's `abi` and `address` inline (the connector only reads the ABI from the contract file when it deploys).
- The Ethereum connector needs a `ws://` URL (`ws://localhost:8546`) and refuses `http(s)`.
- `generated/` is rebuilt every run and is not committed.
