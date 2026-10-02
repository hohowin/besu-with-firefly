// Spike only: deploy Paladin's registry and Noto contracts through the Paladin node, signed by its own derived keys.
// Mirrors the Paladin operator: registry -> noto -> noto-factory -> noto-factory-proxy. Artifacts are from the Paladin v1.0.0 release.
import { readFileSync, writeFileSync } from "node:fs";
const RPC = process.env.PALADIN_RPC || "http://localhost:8548";
let id = 1;
const rpc = async (method, params) => {
  const r = await fetch(RPC, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: id++, method, params }) });
  const j = await r.json(); if (j.error) throw new Error(`${method}: ${j.error.message}`); return j.result;
};
const load = (name) => {
  const t = readFileSync(`artifacts/core_v1alpha1_smartcontractdeployment_${name}.yaml`, "utf8").split("\n");
  const a = t.findIndex((l) => l.startsWith("  abiJSON:")); let e = a + 1;
  while (e < t.length && (t[e].startsWith("    ") || t[e] === "")) e++;
  const abi = JSON.parse(t.slice(a + 1, e).map((l) => l.slice(4)).join("\n"));
  const bytecode = t.find((l) => l.startsWith("  bytecode:")).split(":")[1].trim();
  return { abi, bytecode };
};
const deploy = async (name, from, data) => {
  const { abi, bytecode } = load(name);
  const txId = await rpc("ptx_sendTransaction", [{ type: "public", from, abi, bytecode, data }]);
  for (let i = 0; i < 60; i++) {
    const rc = await rpc("ptx_getTransactionReceipt", [txId]);
    if (rc) { if (!rc.success) throw new Error(`${name} failed: ${JSON.stringify(rc)}`); console.log(name.padEnd(20), rc.contractAddress, "tx", txId); return rc.contractAddress; }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`${name}: no receipt after 60s`);
};
const out = {};
out.registry = await deploy("registry", "registry.operator", [false]);
out.noto = await deploy("noto", "noto.operator", {});
out.notoFactory = await deploy("noto_factory", "noto_factory.operator", {});
const initCall = "0xc4d66de8000000000000000000000000" + out.noto.replace(/^0x/, "");
out.notoFactoryProxy = await deploy("noto_factory_proxy", "noto_factory_proxy.operator", [out.notoFactory, initCall]);
writeFileSync("deployed.json", JSON.stringify(out, null, 2));
console.log(out);
