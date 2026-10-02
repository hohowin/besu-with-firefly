import { readFileSync } from "node:fs";
const evm = process.argv[2] || "shanghai";
const { abi, bytecode } = JSON.parse(readFileSync(`SpikeStore.${evm}.json`));
const { admin } = JSON.parse(readFileSync("demo-addresses.json"));
const base = "http://localhost:5000/api/v1/namespaces/default";
const res = await fetch(`${base}/contracts/deploy?confirm=true`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ contract: bytecode, definition: abi, input: [], key: admin }) });
const text = await res.text();
console.log("HTTP", res.status); console.log(text.slice(0, 1500));
