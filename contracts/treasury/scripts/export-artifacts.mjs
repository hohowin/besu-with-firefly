// Copies the compiled contracts that `stack.py treasury` deploys into compiled/ (committed),
// and writes compiled/SHA256SUMS. Run after `hardhat build`: `npm run build`.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "compiled");
const names = ["CurrencyToken", "FundingRequest"];
const sums = [];

mkdirSync(out, { recursive: true });
for (const name of names) {
  const built = JSON.parse(
    readFileSync(join(root, "artifacts", "contracts", `${name}.sol`, `${name}.json`), "utf8"),
  );
  const text =
    JSON.stringify(
      {
        contractName: name,
        solc: "0.8.28",
        evmVersion: "shanghai",
        abi: built.abi,
        bytecode: built.bytecode,
        deployedBytecodeBytes: (built.deployedBytecode.length - 2) / 2,
      },
      null,
      2,
    ) + "\n";
  writeFileSync(join(out, `${name}.json`), text);
  sums.push(`${createHash("sha256").update(text).digest("hex")} *${name}.json`);
}
writeFileSync(join(out, "SHA256SUMS"), sums.join("\n") + "\n");
console.log(`exported ${names.join(", ")} to compiled/`);
