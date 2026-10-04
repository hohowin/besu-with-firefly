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
| `npm test` | Unit tests of the report parser and the snapshot (no stack needed). |
| `node lib/derive.js "<seed>" [count]` | Prints the wallets Caliper derives from a seed, one per worker. |

## The load

One place sets the load of both layers, as environment variables (defaults in `lib/params.js`):

| Variable | Default | Meaning |
|---|---|---|
| `PERF_WALLETS` | 10 | Wallets, and Caliper workers: worker `i` owns wallet `i` |
| `PERF_TPS` | 20 | Transactions per second offered in all (a multiple of `PERF_WALLETS`) |
| `PERF_TXS` | 600 | Transactions in all (a multiple of `PERF_WALLETS`) |
| `PERF_AMOUNT` | `1000000000000000` | Base units per transfer (0.001 COIN) |

Worker `i` sends to wallet `i+1` (the last one to the first), so every recipient is a verified investor. Caliper takes
`txNumber` and `tps` as totals and splits them across the workers. A round fails if a transaction fails, or if the
sum of the wallets' balances changed.

## Notes

- The token is already deployed, so rounds run with `--caliper-flow-skip-install`, and the network config carries the
  contract's `abi` and `address` inline (the connector only reads the ABI from the contract file when it deploys).
- The Ethereum connector needs a `ws://` URL (`ws://localhost:8546`) and refuses `http(s)`.
- `generated/` is rebuilt every run and is not committed.
