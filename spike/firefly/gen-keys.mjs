// Spike only: generate demo wallets (admin, anson, beatrice) as signer keystores. Demo keys, no real value.
import { Wallet } from "ethers";
import { writeFileSync } from "node:fs";
const PASSWORD = "correcthorsebatterystaple";
const out = {};
for (const name of ["admin", "anson", "beatrice"]) {
  const w = Wallet.createRandom();
  const addr = w.address.slice(2).toLowerCase();
  writeFileSync(`signer-data/keystore/${addr}`, await w.encrypt(PASSWORD));
  writeFileSync(`signer-data/keystore/${addr}.toml`,
`[metadata]
description = "File based configuration"

[signing]
type = "file-based-signer"
key-file = "/data/keystore/${addr}"
password-file = "/data/password"
`);
  out[name] = w.address;
}
writeFileSync("signer-data/password", PASSWORD);
writeFileSync("demo-addresses.json", JSON.stringify(out, null, 2));
console.log(out);
