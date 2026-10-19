# Treasury contracts

`CurrencyToken` (deployed twice, as `CADC` and `GBPC`) and `FundingRequest`. Design: `docs/treasury-use-case/design.md` §3.

| Folder | What |
|---|---|
| `contracts/` | Solidity sources |
| `test/` | Solidity tests (Hardhat 3, no forge-std; `Vm.sol` declares the two cheatcodes used) |
| `compiled/` | **Committed.** ABI and bytecode, solc 0.8.28, evmVersion `shanghai` (plan D-08), with `SHA256SUMS`. `stack.py treasury` deploys these |
| `artifacts/`, `cache/` | Hardhat build output, not committed |

```
npm ci
npm test            # hardhat test solidity
npm run build       # compile, then refresh compiled/ and SHA256SUMS
(cd compiled && sha256sum -c SHA256SUMS)
```

After changing a `.sol` file, run `npm run build` and commit `compiled/` with it.
