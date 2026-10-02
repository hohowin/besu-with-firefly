// Spike only: write config for three Paladin nodes (node1 notary and registry admin, node2 Anson, node3 Beatrice).
// node1 keeps the mnemonic it already used so the contracts it deployed stay valid. Demo mnemonics, no value.
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import { randomBytes } from "node:crypto";
const { Mnemonic } = createRequire(new URL("../firefly/package.json", import.meta.url))("ethers");
const dep = JSON.parse(readFileSync("deployed.json"));
const old = readFileSync(process.argv[2], "utf8");
const mnemonics = { node1: old.match(/inline: "([^"]+)"/)[1] };
for (const n of ["node2", "node3"]) {
  const f = `config/${n}/pldconf.paladin.yaml`;
  mnemonics[n] = existsSync(f) ? readFileSync(f, "utf8").match(/inline: "([^"]+)"/)[1] : Mnemonic.fromEntropy(randomBytes(16)).phrase;
}
for (const n of ["node1", "node2", "node3"]) {
  mkdirSync(`config/${n}`, { recursive: true });
  writeFileSync(`config/${n}/pldconf.paladin.yaml`, `nodeName: ${n}
log:
  level: debug
blockchain:
  http:
    url: http://host.docker.internal:8545
  ws:
    url: ws://host.docker.internal:8546
db:
  type: postgres
  postgres:
    dsn: "postgres://postgres:spike-pw@postgres:5432/${n}?sslmode=disable"
    autoMigrate: true
    migrationsDir: /app/db/migrations/postgres
rpcServer:
  http:
    address: 0.0.0.0
    port: 8548
  ws:
    address: 0.0.0.0
    port: 8549
wallets:
- name: wallet1
  keySelector: ".*"
  signer:
    keyDerivation:
      type: bip32
      seedKey:
        name: seed
    keyStore:
      type: static
      static:
        keys:
          seed:
            encoding: none
            inline: "${mnemonics[n]}"
domains:
  noto:
    plugin:
      type: c-shared
      library: /app/domains/libnoto.so
    config:
      factoryVersion: 2
    registryAddress: ${dep.notoFactoryProxy}
registries:
  evm-registry:
    plugin:
      type: c-shared
      library: /app/registries/libevm.so
    config:
      contractAddress: ${dep.registry}
transports:
  grpc:
    plugin:
      type: c-shared
      library: /app/transports/libgrpc.so
    config:
      port: 9000
      address: 0.0.0.0
      externalHostname: paladin-${n}
      tls:
        enabled: true
        clientAuth: true
        certFile: /certs/tls.crt
        keyFile: /certs/tls.key
        caFile: /certs/ca.crt
`);
}
console.log("wrote config for node1, node2, node3");
