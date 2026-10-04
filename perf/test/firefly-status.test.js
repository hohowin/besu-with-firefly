'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { isSucceeded, invokeUrl, invokeBody } = require('../lib/firefly-status');

test('only a Succeeded operation behind an HTTP 2xx counts as a success', () => {
    assert.strictEqual(isSucceeded(true, { id: 'op', status: 'Succeeded', tx: 'tx' }), true);
});

test('pending, failed, unknown and empty statuses are failures, never successes', () => {
    for (const status of ['Pending', 'Initialized', 'Failed', 'Retry', '', 'succeeded', 'SUCCEEDED', undefined, null, 5]) {
        assert.strictEqual(isSucceeded(true, { id: 'op', status }), false, `status ${JSON.stringify(status)}`);
    }
});

test('an HTTP error is a failure even if the body says Succeeded', () => {
    assert.strictEqual(isSucceeded(false, { status: 'Succeeded' }), false);
});

test('a body that is not an operation is a failure', () => {
    for (const body of [null, undefined, 'Succeeded', [], 42]) {
        assert.strictEqual(isSucceeded(true, body), false, `body ${JSON.stringify(body)}`);
    }
});

test('the request goes to the contract API with confirm=true, and names the signing key', () => {
    assert.strictEqual(
        invokeUrl({ url: 'http://localhost:5000', api: 'coin' }, 'transfer'),
        'http://localhost:5000/api/v1/namespaces/default/apis/coin/invoke/transfer?confirm=true'
    );
    assert.deepStrictEqual(
        invokeBody({ sender: '0xabc', inputs: { _to: '0xdef', _amount: '5' } }),
        { input: { _to: '0xdef', _amount: '5' }, key: '0xabc' }
    );
});
