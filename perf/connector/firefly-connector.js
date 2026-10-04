'use strict';
// Caliper connector for the FireFly layer: sends each request as a call to FireFly's contract API
// (`POST /apis/<api>/invoke/<method>?confirm=true`) and waits for the final operation. Caliper has no FireFly
// connector, so this is the small custom one (spike Risk 5). The same workload module drives it as the chain
// layer, so the two reports differ only by the path the transfer takes.
const { ConnectorBase, TxStatus, CaliperUtils, ConfigUtil } = require('@hyperledger/caliper-core');
const { isSucceeded, invokeUrl, invokeBody } = require('../lib/firefly-status');

const REQUEST_TIMEOUT_MS = 150000; // `confirm=true` holds the request until the transaction is final

class FireFlyConnector extends ConnectorBase {
    constructor(workerIndex) {
        super(workerIndex, 'firefly');
        this.config = require(CaliperUtils.resolvePath(ConfigUtil.get(ConfigUtil.keys.NetworkConfig))).firefly;
    }

    async init() {}
    async installSmartContract() {}
    async prepareWorkerArguments() { return []; }
    async getContext() { return {}; }
    async releaseContext() {}

    async _sendSingleRequest(request) {
        const status = new TxStatus();
        try {
            const response = await fetch(invokeUrl(this.config, request.verb), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(invokeBody(request)),
                signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS)
            });
            const body = await response.json().catch(() => null);
            if (isSucceeded(response.ok, body)) {
                status.SetID(body.tx);
                status.SetResult(body);
                status.SetVerification(true);
                status.SetStatusSuccess();
            } else {
                status.SetStatusFail();
            }
        } catch (error) {
            status.SetStatusFail();
        }
        return status;
    }
}

module.exports.ConnectorFactory = async (workerIndex) => new FireFlyConnector(workerIndex);
