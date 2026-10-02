// Spike only: Noto across three Paladin nodes. node1 = notary, node2 = Anson, node3 = Beatrice.
import { readFileSync } from "node:fs";
const P = { node1: 8548, node2: 8648, node3: 8748 };
const abis = process.env.NOTO_ABIS;
const priv = JSON.parse(readFileSync(`${abis}/INotoPrivate.json`)); const abi = priv.abi || priv;
const ctor = [{ type: "constructor", inputs: [{ name: "notary", type: "string" }, { name: "notaryMode", type: "string" }] }];
let id = 1;
const rpc = async (node, method, params) => {
  const r = await fetch(`http://localhost:${P[node]}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: id++, method, params }) });
  const j = await r.json(); if (j.error) throw new Error(`${method}@${node}: ${j.error.message}`); return j.result;
};
const receipt = async (node, txId) => {
  for (let i = 0; i < 120; i++) {
    const rc = await rpc(node, "ptx_getTransactionReceipt", [txId]);
    if (rc) { if (!rc.success) throw new Error("tx failed: " + JSON.stringify(rc).slice(0, 700)); return rc; }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("no receipt in 120s");
};
const states = async (node, token) => {
  const schemas = await rpc(node, "pstate_listSchemas", ["noto"]);
  const out = [];
  for (const s of schemas) { const st = await rpc(node, "pstate_queryContractStates", ["noto", token, s.id, { limit: 50 }, "all"]).catch(() => []); out.push(...st.map((x) => ({ schema: s.signature?.slice(0, 40), data: x.data }))); }
  return out;
};
const show = async (label, token) => { for (const n of Object.keys(P)) { const s = await states(n, token); console.log(`  ${label} | ${n} sees ${s.length} state(s):`, JSON.stringify(s.map((x) => x.data))); } };

const dep = await receipt("node1", await rpc("node1", "ptx_sendTransaction", [{ type: "private", domain: "noto", from: "notary@node1", abi: ctor, data: { notary: "notary@node1", notaryMode: "basic" } }]));
const token = dep.contractAddress; console.log("token", token);
const call = (node, from, fn, data) => rpc(node, "ptx_sendTransaction", [{ type: "private", domain: "noto", from, to: token, abi, function: fn, data }]).then((t) => receipt(node, t));
await call("node1", "notary@node1", "mint", { to: "anson@node2", amount: 100, data: "0x" });
console.log("minted 100 to anson@node2 (submitted on node1)");
await new Promise((r) => setTimeout(r, 3000));
await show("after mint", token);
await call("node2", "anson@node2", "transfer", { to: "beatrice@node3", amount: 40, data: "0x" });
console.log("transferred 40 anson@node2 -> beatrice@node3 (submitted on node2)");
await new Promise((r) => setTimeout(r, 3000));
await show("after transfer", token);
const bal = (node, who) => rpc(node, "ptx_call", [{ type: "private", domain: "noto", from: who, to: token, abi, function: "balanceOf", data: { account: who } }]);
console.log("anson balance on node2:", JSON.stringify(await bal("node2", "anson@node2")));
console.log("beatrice balance on node3:", JSON.stringify(await bal("node3", "beatrice@node3")));
