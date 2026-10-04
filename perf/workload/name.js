'use strict';
// Smoke workload: COIN.name(), a read-only call, so nothing is written to the chain.
const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

class NameWorkload extends WorkloadModuleBase {
    async submitTransaction() {
        return this.sutAdapter.sendRequests({
            contract: 'COIN',
            verb: 'name',
            args: [],
            readOnly: true
        });
    }
}

module.exports.createWorkloadModule = () => new NameWorkload();
