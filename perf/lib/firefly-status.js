'use strict';
// What the FireFly connector sends and when it counts a transaction as done. Pure, so it is tested without a
// stack. The rule is the same as the CLI's: only a `Succeeded` operation is a success. A pending or unknown
// one is not, because the write may still land and a benchmark must not count it as done.

function isSucceeded(httpOk, body) {
    return httpOk === true && body !== null && typeof body === 'object' && !Array.isArray(body) && body.status === 'Succeeded';
}

function invokeUrl(config, method) {
    return `${config.url}/api/v1/namespaces/default/apis/${config.api}/invoke/${method}?confirm=true`;
}

function invokeBody(request) {
    return { input: request.inputs, key: request.sender };
}

module.exports = { isSucceeded, invokeUrl, invokeBody };
