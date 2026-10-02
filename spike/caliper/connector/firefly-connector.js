'use strict';
// Spike only: minimal Caliper connector that sends SpikeStore.set() through FireFly's contract invoke API.
// Same workload as the chain-layer round, so the difference between the two reports is the gateway overhead.
const { ConnectorBase, TxStatus, CaliperUtils, ConfigUtil } = require('@hyperledger/caliper-core');

class FireFlyConnector extends ConnectorBase {
    constructor(workerIndex) {
        super(workerIndex, 'firefly');
        this.cfg = require(CaliperUtils.resolvePath(ConfigUtil.get(ConfigUtil.keys.NetworkConfig))).firefly;
    }
    async init() {}
    async installSmartContract() {}
    async prepareWorkerArguments() { return []; }
    async getContext() { return {}; }
    async releaseContext() {}

    async _sendSingleRequest(request) {
        const status = new TxStatus();
        const u256 = { type: 'integer', details: { type: 'uint256' } };
        try {
            const res = await fetch(`${this.cfg.url}/api/v1/namespaces/default/contracts/invoke?confirm=true`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    location: { address: this.cfg.contractAddress },
                    method: { name: request.verb, params: [{ name: 'v', schema: u256 }], returns: [] },
                    input: { v: request.args[0] },
                    key: this.cfg.key
                })
            });
            const body = await res.json();
            if (res.ok && body.status === 'Succeeded') {
                status.SetID(body.tx);
                status.SetResult(body);
                status.SetVerification(true);
                status.SetStatusSuccess();
            } else {
                status.SetStatusFail();
            }
        } catch (err) {
            status.SetStatusFail();
        }
        return status;
    }
}

module.exports.ConnectorFactory = async (workerIndex) => new FireFlyConnector(workerIndex);
