'use strict';
// Prints the wallets Caliper's Ethereum connector derives from a seed, one per worker index, with
// the same call the connector makes. Used as the test vector for the Python derivation.
//   node lib/derive.js "<seed>" [count]
const EthereumHDKey = require('ethereumjs-wallet/hdkey');

const seed = process.argv[2];
const count = Number(process.argv[3] || 3);
if (!seed) {
    console.error('usage: node lib/derive.js "<seed>" [count]');
    process.exit(2);
}
const hdwallet = EthereumHDKey.fromMasterSeed(seed);
for (let worker = 0; worker < count; worker++) {
    const wallet = hdwallet.derivePath(`m/44'/60'/${worker}'/0/0`).getWallet();
    console.log(JSON.stringify({ worker, address: wallet.getChecksumAddressString().toLowerCase(), privateKey: wallet.getPrivateKeyString() }));
}
