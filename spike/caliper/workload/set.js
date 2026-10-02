'use strict';
// Spike only: each transaction calls SpikeStore.set(n) directly over JSON-RPC (chain layer, no FireFly).
const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

class SetWorkload extends WorkloadModuleBase {
    async submitTransaction() {
        const value = Math.floor(Math.random() * 1000000);
        return this.sutAdapter.sendRequests({
            contract: 'SpikeStore',
            verb: 'set',
            args: [value],
            readOnly: false
        });
    }
}

module.exports.createWorkloadModule = () => new SetWorkload();
