'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { readParams, DEFAULT_SEED } = require('../lib/params');

test('the defaults are 10 wallets, 5 TPS offered in all, 300 transactions, 0.001 COIN', () => {
    assert.deepStrictEqual(readParams({}), {
        seed: DEFAULT_SEED,
        wallets: 10,
        tpsTotal: 5,
        txTotal: 300,
        amount: '1000000000000000'
    });
});

test('every value can be overridden from the environment', () => {
    const params = readParams({ PERF_WALLETS: '4', PERF_TPS: '2.5', PERF_TXS: '40', PERF_AMOUNT: '7', PERF_SEED: 'x' });
    assert.deepStrictEqual(params, { seed: 'x', wallets: 4, tpsTotal: 2.5, txTotal: 40, amount: '7' });
});

test('bad values are refused with the variable named', () => {
    for (const [name, value] of [['PERF_WALLETS', '0'], ['PERF_WALLETS', 'x'], ['PERF_TPS', '0'], ['PERF_TPS', '-1'],
        ['PERF_TXS', '1.5'], ['PERF_AMOUNT', '0'], ['PERF_AMOUNT', '1.5']]) {
        assert.throws(() => readParams({ [name]: value }), new RegExp(name), `${name}=${value}`);
    }
});

test('the transaction count must split evenly over the workers', () => {
    assert.throws(() => readParams({ PERF_WALLETS: '10', PERF_TXS: '25' }), /multiple of PERF_WALLETS/);
});
