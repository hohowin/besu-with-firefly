import solc from "solc";
import { readFileSync, writeFileSync } from "node:fs";
const evm = process.argv[2] || "shanghai";
const src = readFileSync("contracts/SpikeStore.sol", "utf8");
const input = { language: "Solidity", sources: { "SpikeStore.sol": { content: src } },
  settings: { evmVersion: evm, optimizer: { enabled: true, runs: 200 }, outputSelection: { "*": { "*": ["abi", "evm.bytecode.object", "evm.deployedBytecode.object"] } } } };
const out = JSON.parse(solc.compile(JSON.stringify(input)));
if (out.errors?.some(e => e.severity === "error")) { console.error(out.errors); process.exit(1); }
const c = out.contracts["SpikeStore.sol"].SpikeStore;
writeFileSync(`SpikeStore.${evm}.json`, JSON.stringify({ abi: c.abi, bytecode: "0x" + c.evm.bytecode.object }, null, 1));
console.log(evm, "bytecode bytes:", c.evm.bytecode.object.length / 2, "deployed bytes:", c.evm.deployedBytecode.object.length / 2);
