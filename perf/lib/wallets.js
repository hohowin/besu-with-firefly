'use strict';
// The benchmark wallets: worker i owns the key at m/44'/60'/i'/0/0 of the seed, exactly as Caliper's Ethereum
// connector derives it for `fromAddressSeed`. `python scripts/stack.py perf-setup` derives the same wallets.
const EthereumHDKey = require('ethereumjs-wallet/hdkey');

function deriveAddresses(seed, count) {
    const hdwallet = EthereumHDKey.fromMasterSeed(seed);
    const addresses = [];
    for (let worker = 0; worker < count; worker++) {
        const wallet = hdwallet.derivePath(`m/44'/60'/${worker}'/0/0`).getWallet();
        addresses.push(wallet.getChecksumAddressString().toLowerCase());
    }
    return addresses;
}

module.exports = { deriveAddresses };
