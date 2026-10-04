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
| `npm run prepare-run` | Writes `generated/` (token address and ABI, Caliper network config) from `deployed-addresses.json`. Run by every round. |
| `node lib/derive.js "<seed>" [count]` | Prints the wallets Caliper derives from a seed, one per worker. |

## Notes

- The token is already deployed, so rounds run with `--caliper-flow-skip-install`, and the network config carries the
  contract's `abi` and `address` inline (the connector only reads the ABI from the contract file when it deploys).
- The Ethereum connector needs a `ws://` URL (`ws://localhost:8546`) and refuses `http(s)`.
- `generated/` is rebuilt every run and is not committed.
