'use strict';
// Worker i sends COIN.transfer(wallet[(i + 1) mod N], amount) from its own wallet. Every recipient is another
// benchmark wallet of the same layer, so every recipient is a verified investor. The same module runs on both
// layers: the chain layer signs with the key Caliper derives for the worker (wallets 0 to N-1), the FireFly layer
// asks FireFly's signer to sign for wallets N to 2N-1 (`offset`). The layers never share a wallet, because
// FireFly's evmconnect works out a key's next nonce from its own records and would fall behind a key that
// something else sent from.
const { WorkloadModuleBase } = require('@hyperledger/caliper-core');
const { deriveAddresses } = require('../lib/wallets');

class TransferWorkload extends WorkloadModuleBase {
    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
        await super.initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext);
        const { seed, amount, offset } = roundArguments;
        const addresses = deriveAddresses(seed, offset + totalWorkers);
        this.sender = addresses[offset + workerIndex];
        this.recipient = addresses[offset + ((workerIndex + 1) % totalWorkers)];
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
