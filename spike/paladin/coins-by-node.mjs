// Spike only: list the Noto coin states (amount and owner key) that each Paladin node can see for a token.
const token = process.argv[2];
const P = { "node1 (notary)": 8548, "node2 (Anson)": 8648, "node3 (Beatrice)": 8748 };
let id = 1;
const rpc = async (port, method, params) => { const r = await fetch(`http://localhost:${port}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: id++, method, params }) }); const j = await r.json(); if (j.error) throw new Error(j.error.message); return j.result; };
for (const [label, port] of Object.entries(P)) {
  const schemas = await rpc(port, "pstate_listSchemas", ["noto"]);
  const coins = [];
  for (const s of schemas) {
    const st = await rpc(port, "pstate_queryContractStates", ["noto", token, s.id, { limit: 100 }, "all"]);
    for (const x of st) if (x.data && x.data.amount !== undefined) coins.push(x.data.amount);
  }
  console.log(label.padEnd(18), "coin amounts visible:", JSON.stringify(coins.sort((a, b) => a - b)));
}
