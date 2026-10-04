'use strict';
// Writes generated/ for Caliper from what `stack.py deploy` left behind: the token address
// (deployed-addresses.json) and the token ABI (the pinned T-REX package). The address is not known until
// deploy, so none of this can be committed.
//   generated/COIN.json            the ABI file the connector expects
//   generated/ethereum-smoke.json  network config for the smoke round (read-only, admin key)
//   generated/ethereum.json        network config for the chain layer (one derived wallet per worker)
//   generated/firefly.json         network config for the FireFly layer (the custom connector)
//   generated/benchmark-chain.yaml and benchmark-firefly.yaml   the transfer round, the same load on a different
//                                  set of wallets each (chain: 0 to N-1, FireFly: N to 2N-1)
const fs = require('fs');
const path = require('path');
const { readParams } = require('./params');

const root = path.resolve(__dirname, '..', '..');
const out = path.resolve(__dirname, '..', 'generated');
const TRANSFER_GAS = 500000; // an upper bound; the chain charges no gas (min gas price 0)

function readJson(file, hint) {
    if (!fs.existsSync(file)) {
        throw new Error(`${file} not found. ${hint}`);
    }
    return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function readDeployment() {
    const addresses = readJson(path.join(root, 'deployed-addresses.json'), 'Run `python scripts/stack.py deploy` first.');
    if (!addresses.token) {
        throw new Error('deployed-addresses.json has no "token" entry. Run `python scripts/stack.py deploy` first.');
    }
    const artifact = readJson(
        path.join(root, 'contracts', 'node_modules', '@tokenysolutions', 't-rex', 'artifacts', 'contracts', 'token', 'Token.sol', 'Token.json'),
        'Run `npm ci` in contracts/ first.'
    );
    return { token: addresses.token, abi: artifact.abi };
}

// Caliper takes `txNumber` and `tps` as totals for the round and splits them across the workers
// (measured: txNumber 60 and tps 2 with 10 workers gave 60 transactions in all at about 2 TPS in all).
function benchmarkYaml(params, offset) {
    return `test:
  name: coin-transfer
  description: COIN.transfer from ${params.wallets} wallets, ${params.tpsTotal} TPS offered in all
  workers:
    type: local
    number: ${params.wallets}
  rounds:
    - label: transfer
      txNumber: ${params.txTotal}
      rateControl:
        type: fixed-rate
        opts:
          tps: ${params.tpsTotal}
      workload:
        module: workload/transfer.js
        arguments:
          seed: ${JSON.stringify(params.seed)}
          amount: ${JSON.stringify(params.amount)}
          offset: ${offset}
`;
}

function prepare(params = readParams()) {
    const { token, abi } = readDeployment();
    const wallets = readJson(path.join(root, 'network-config', 'wallets.json'), 'Run `python scripts/stack.py init` first.');
    const admin = wallets.wallets.find((w) => w.name === 'admin');
    const contract = { path: 'generated/COIN.json', abi, address: token, estimateGas: false, gas: { transfer: TRANSFER_GAS } };

    fs.mkdirSync(out, { recursive: true });
    fs.writeFileSync(path.join(out, 'COIN.json'), JSON.stringify({ name: 'COIN', abi, bytecode: '0x' }, null, 2));
    fs.writeFileSync(path.join(out, 'ethereum-smoke.json'), JSON.stringify({
        caliper: { blockchain: 'ethereum' },
        ethereum: {
            url: 'ws://localhost:8546',
            fromAddress: admin.address,
            fromAddressPrivateKey: admin.privateKey,
            transactionConfirmationBlocks: 1,
            contracts: { COIN: contract }
        }
    }, null, 2));
    fs.writeFileSync(path.join(out, 'ethereum.json'), JSON.stringify({
        caliper: { blockchain: 'ethereum' },
        ethereum: {
            url: 'ws://localhost:8546',
            fromAddressSeed: params.seed,
            transactionConfirmationBlocks: 1,
            contracts: { COIN: contract }
        }
    }, null, 2));
    fs.writeFileSync(path.join(out, 'firefly.json'), JSON.stringify({
        caliper: { blockchain: './connector/firefly-connector.js' },
        firefly: { url: process.env.FIREFLY_URL || 'http://localhost:5000', api: 'coin' }
    }, null, 2));
    fs.writeFileSync(path.join(out, 'benchmark-chain.yaml'), benchmarkYaml(params, 0));
    fs.writeFileSync(path.join(out, 'benchmark-firefly.yaml'), benchmarkYaml(params, params.wallets));
    return { token, params };
}

module.exports = { prepare, benchmarkYaml, TRANSFER_GAS };

if (require.main === module) {
    const { token } = prepare();
    console.log(`prepared generated/ for token ${token}`);
}
