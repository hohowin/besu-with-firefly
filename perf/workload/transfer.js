'use strict';
// Worker i sends COIN.transfer(wallet[(i + 1) mod N], amount) from its own wallet. Every recipient is another
// benchmark wallet, so every recipient is a verified investor. The same module runs on both layers: the chain
// layer signs with the key Caliper derives for the worker, the FireFly layer asks FireFly's signer to sign
// for the same address.
const { WorkloadModuleBase } = require('@hyperledger/caliper-core');
const { deriveAddresses } = require('../lib/wallets');

class TransferWorkload extends WorkloadModuleBase {
    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
        await super.initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext);
        const { seed, amount } = roundArguments;
        const addresses = deriveAddresses(seed, totalWorkers);
        this.sender = addresses[workerIndex];
        this.recipient = addresses[(workerIndex + 1) % totalWorkers];
        this.amount = String(amount);
    }

    async submitTransaction() {
        return this.sutAdapter.sendRequests({
            contract: 'COIN',
            verb: 'transfer',
            args: [this.recipient, this.amount],
            // Used by the FireFly connector, which names the signing key and the argument names; the
            // Ethereum connector ignores them.
            sender: this.sender,
            inputs: { _to: this.recipient, _amount: this.amount },
            readOnly: false
        });
    }
}

module.exports.createWorkloadModule = () => new TransferWorkload();
