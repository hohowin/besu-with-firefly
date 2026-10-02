import { readFileSync } from "node:fs";
const art = JSON.parse(readFileSync(process.argv[2]));
const { admin } = JSON.parse(readFileSync("demo-addresses.json"));
const res = await fetch("http://localhost:5000/api/v1/namespaces/default/contracts/deploy?confirm=true", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ contract: art.bytecode, definition: art.abi, input: [], key: admin }) });
const t = await res.text(); let j; try { j = JSON.parse(t); } catch {}
console.log(art.contractName, "HTTP", res.status, j ? `status=${j.status} address=${j.output?.contractLocation?.address}` : t.slice(0, 400));
