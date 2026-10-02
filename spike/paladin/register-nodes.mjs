// Spike only: register node1, node2 and node3 in the EVM registry, mirroring the Paladin operator's PaladinRegistration flow.
// 1) node1's registry.operator key calls registerIdentity(parent 0x0, nodeName, nodeKeyAddress)
// 2) each node calls setIdentityProperty(identityHash, "transport.grpc", localTransportDetails) with its own registry.<node> key
import { readFileSync } from "node:fs";
const nodes = { node1: 8548, node2: 8648, node3: 8748 };
const dep = JSON.parse(readFileSync("deployed.json"));
let id = 1;
const rpc = async (port, method, params) => {
  const r = await fetch(`http://localhost:${port}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: id++, method, params }) });
  const j = await r.json(); if (j.error) throw new Error(`${method}@${port}: ${j.error.message}`); return j.result;
};
const regAbi = (() => {
  const t = readFileSync("artifacts/core_v1alpha1_smartcontractdeployment_registry.yaml", "utf8").split("\n");
  const a = t.findIndex((l) => l.startsWith("  abiJSON:")); let e = a + 1;
  while (e < t.length && (t[e].startsWith("    ") || t[e] === "")) e++;
  return JSON.parse(t.slice(a + 1, e).map((l) => l.slice(4)).join("\n"));
})();
const send = async (port, from, fn, data) => {
  const txId = await rpc(port, "ptx_sendTransaction", [{ type: "public", from, to: dep.registry, abi: regAbi, function: fn, data }]);
  for (let i = 0; i < 90; i++) {
    const rc = await rpc(port, "ptx_getTransactionReceipt", [txId]);
    if (rc) { if (!rc.success) throw new Error(`${fn} failed: ${JSON.stringify(rc).slice(0, 500)}`); return rc; }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`${fn}: no receipt`);
};
const ZERO = "0x" + "00".repeat(32);
for (const [name, port] of Object.entries(nodes)) {
  const key = await rpc(port, "keymgr_resolveKey", [`registry.${name}`, "ecdsa:secp256k1", "eth_address"]);
  await send(nodes.node1, "registry.operator", "registerIdentity", { parentIdentityHash: ZERO, name, owner: key.verifier.verifier });
  console.log("registered identity", name, "owner", key.verifier.verifier);
}
const entries = await rpc(nodes.node1, "reg_queryEntries", ["evm-registry", { limit: 20 }, "any"]);
console.log("registry entries:", JSON.stringify(entries).slice(0, 700));
for (const [name, port] of Object.entries(nodes)) {
  const entry = entries.find((e) => e.name === name);
  if (!entry) throw new Error(`entry for ${name} not found`);
  const details = await rpc(port, "transport_localTransportDetails", ["grpc"]);
  await send(port, `registry.${name}`, "setIdentityProperty", { identityHash: entry.id, name: "transport.grpc", value: details });
  console.log("set transport.grpc for", name, "identity", entry.id);
}
