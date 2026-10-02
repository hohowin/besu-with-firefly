// Spike only: single-node Noto flow through one Paladin node. Deploy token, mint, transfer, read balances.
import { readFileSync } from "node:fs";
const RPC = process.env.PALADIN_RPC || "http://localhost:8548";
const ABIS = process.env.NOTO_ABIS; // folder with INotoPrivate.json from the Paladin abis.tar.gz release asset
let id = 1;
const rpc = async (method, params) => {
  const r = await fetch(RPC, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: id++, method, params }) });
  const j = await r.json(); if (j.error) throw new Error(`${method}: ${j.error.message}`); return j.result;
};
const waitReceipt = async (txId) => {
  for (let i = 0; i < 90; i++) {
    const rc = await rpc("ptx_getTransactionReceipt", [txId]);
    if (rc) { if (!rc.success) throw new Error("tx failed: " + JSON.stringify(rc).slice(0, 600)); return rc; }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("no receipt after 90s");
};
const priv = JSON.parse(readFileSync(`${ABIS}/INotoPrivate.json`));
const abi = priv.abi || priv;
const ctor = [{ type: "constructor", inputs: [{ name: "notary", type: "string" }, { name: "notaryMode", type: "string" }] }];

const deployTx = await rpc("ptx_sendTransaction", [{ type: "private", domain: "noto", from: "notary@node1", abi: ctor, data: { notary: "notary@node1", notaryMode: "basic" } }]);
const rc = await waitReceipt(deployTx);
const token = rc.contractAddress;
console.log("deployed Noto token:", token);

const call = async (fn, from, data) => waitReceipt(await rpc("ptx_sendTransaction", [{ type: "private", domain: "noto", from, to: token, abi, function: fn, data }]));
await call("mint", "notary@node1", { to: "anson@node1", amount: 100, data: "0x" });
console.log("minted 100 to anson");
await call("transfer", "anson@node1", { to: "beatrice@node1", amount: 40, data: "0x" });
console.log("transferred 40 anson -> beatrice");
const bal = async (who) => rpc("ptx_call", [{ type: "private", domain: "noto", from: who, to: token, abi, function: "balanceOf", data: { account: who } }]);
for (const w of ["anson@node1", "beatrice@node1"]) console.log("balance", w, JSON.stringify(await bal(w)));
