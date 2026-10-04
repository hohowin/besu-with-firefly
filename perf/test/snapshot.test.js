'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { buildSnapshot, readGenesisSettings } = require('../lib/snapshot');

const GENESIS = { config: { qbft: { blockperiodseconds: 2 } }, gasLimit: '0x1fffffffffffff' };
const PARAMS = { wallets: 10, tpsTotal: 20, txTotal: 600, amount: '1000000000000000' };

test('reads the block period and gas limit from the genesis', () => {
    assert.deepStrictEqual(readGenesisSettings(GENESIS), {
        blockPeriodSeconds: 2,
        gasLimit: '0x1fffffffffffff',
        gasLimitDecimal: '9007199254740991',
    });
});

test('refuses a genesis without a block period, so numbers are never written without it', () => {
    assert.throws(() => readGenesisSettings({ config: {}, gasLimit: '0x1' }), /block period/);
});

test('the snapshot holds the layer, the load, the chain settings and the versions', () => {
    const snapshot = buildSnapshot({
        layer: 'chain',
        params: PARAMS,
        genesis: GENESIS,
        topology: { validators: 1, rpcNodes: 1 },
        versions: { besu: 'hyperledger/besu:26.8.1', caliper: '0.6.0', node: 'v24.11.1' },
        now: new Date('2026-10-04T15:00:00Z'),
    });
    assert.strictEqual(snapshot.layer, 'chain');
    assert.strictEqual(snapshot.generatedAt, '2026-10-04T15:00:00.000Z');
    assert.deepStrictEqual(snapshot.load, { workers: 10, offeredTpsTotal: 20, offeredTpsPerWorker: 2, transactions: 600, amount: '1000000000000000' });
    assert.strictEqual(snapshot.chain.blockPeriodSeconds, 2);
    assert.deepStrictEqual(snapshot.topology, { validators: 1, rpcNodes: 1 });
    assert.strictEqual(snapshot.versions.caliper, '0.6.0');
});

test('two layers with the same load differ only in the layer and the time', () => {
    const make = (layer, now) =>
        buildSnapshot({ layer, params: PARAMS, genesis: GENESIS, topology: { validators: 1, rpcNodes: 1 }, versions: {}, now: new Date(now) });
    const a = make('chain', '2026-10-04T15:00:00Z');
    const b = make('firefly', '2026-10-04T16:00:00Z');
    delete a.layer; delete a.generatedAt; delete b.layer; delete b.generatedAt;
    assert.deepStrictEqual(a, b);
});

test('the benchmark file offers the totals, which Caliper splits across the workers', () => {
    const { benchmarkYaml } = require('../lib/prepare');
    const yaml = benchmarkYaml({ ...PARAMS, seed: 's' });
    assert.match(yaml, /number: 10\n/);
    assert.match(yaml, /txNumber: 600\n/);
    assert.match(yaml, /tps: 20\n/);
});
