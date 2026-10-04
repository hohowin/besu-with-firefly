'use strict';
// Writes generated/COIN.json and generated/ethereum.json for Caliper from what `stack.py deploy` left
// behind: the token address (deployed-addresses.json) and the token ABI (the pinned T-REX package).
// The address is not known until deploy, so the Caliper network config cannot be committed.
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..', '..');
const out = path.resolve(__dirname, '..', 'generated');

function readJson(file, hint) {
    if (!fs.existsSync(file)) {
        throw new Error(`${file} not found. ${hint}`);
    }
    return JSON.parse(fs.readFileSync(file, 'utf8'));
}

const addresses = readJson(path.join(root, 'deployed-addresses.json'), 'Run `python scripts/stack.py deploy` first.');
const artifact = readJson(
    path.join(root, 'contracts', 'node_modules', '@tokenysolutions', 't-rex', 'artifacts', 'contracts', 'token', 'Token.sol', 'Token.json'),
    'Run `npm ci` in contracts/ first.'
);
const wallets = readJson(path.join(root, 'network-config', 'wallets.json'), 'Run `python scripts/stack.py init` first.');
const admin = wallets.wallets.find((w) => w.name === 'admin');
if (!addresses.token) {
    throw new Error('deployed-addresses.json has no "token" entry. Run `python scripts/stack.py deploy` first.');
}

fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, 'COIN.json'), JSON.stringify({ name: 'COIN', abi: artifact.abi, bytecode: '0x' }, null, 2));
fs.writeFileSync(path.join(out, 'ethereum.json'), JSON.stringify({
    caliper: { blockchain: 'ethereum' },
    ethereum: {
        url: 'ws://localhost:8546',
        fromAddress: admin.address,
        fromAddressPrivateKey: admin.privateKey,
        transactionConfirmationBlocks: 1,
        contracts: {
            COIN: { path: 'generated/COIN.json', abi: artifact.abi, address: addresses.token, estimateGas: false }
        }
    }
}, null, 2));
console.log(`prepared generated/ for token ${addresses.token}`);
