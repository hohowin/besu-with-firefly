const address = process.argv[2];
const base = "http://localhost:5000/api/v1/namespaces/default";
const { anson } = JSON.parse((await import("node:fs")).readFileSync("demo-addresses.json"));
const u256 = { type: "integer", details: { type: "uint256" } };
const body = (v) => ({ idempotencyKey: "spike-idem-001", location: { address }, method: { name: "set", params: [{ name: "v", schema: u256 }], returns: [] }, input: { v }, key: anson });
for (const v of [7, 8]) {
  const r = await fetch(base + "/contracts/invoke?confirm=true", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body(v)) });
  const t = await r.text(); console.log("attempt value", v, "HTTP", r.status, t.slice(0, 220));
}
const q = await fetch(base + "/contracts/query", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ location: { address }, method: { name: "get", params: [], returns: [{ name: "", schema: u256 }] }, input: {} }) });
console.log("final stored value:", await q.text());
