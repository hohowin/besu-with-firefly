'use strict';
// The load of a round, one place for both layers. Override with PERF_WALLETS, PERF_TPS, PERF_TXS, PERF_AMOUNT.
// The defaults (5 TPS offered) are below what FireFly can take on this setup (about 8 TPS, see README), so
// every transaction of a default round succeeds on both layers.
// PERF_SEED must equal PERF_SEED in src/core/perf/wallets.py (a Python test checks the two agree).

const DEFAULT_SEED = 'besu-with-firefly perf demo seed';

function positiveInteger(name, value) {
    const number = Number(value);
    if (!Number.isInteger(number) || number < 1) {
        throw new Error(`${name} must be a whole number of at least 1, got ${JSON.stringify(value)}`);
    }
    return number;
}

function positiveNumber(name, value) {
    const number = Number(value);
    if (!Number.isFinite(number) || number <= 0) {
        throw new Error(`${name} must be a number above 0, got ${JSON.stringify(value)}`);
    }
    return number;
}

function readParams(env = process.env) {
    const params = {
        seed: env.PERF_SEED || DEFAULT_SEED,
        wallets: positiveInteger('PERF_WALLETS', env.PERF_WALLETS || 10),
        tpsTotal: positiveNumber('PERF_TPS', env.PERF_TPS || 5),
        txTotal: positiveInteger('PERF_TXS', env.PERF_TXS || 300),
        amount: String(env.PERF_AMOUNT || '1000000000000000'), // 0.001 COIN in base units
    };
    if (!/^\d+$/.test(params.amount) || params.amount === '0') {
        throw new Error(`PERF_AMOUNT must be a positive whole number of base units, got ${JSON.stringify(params.amount)}`);
    }
    if (params.txTotal % params.wallets !== 0) {
        throw new Error(`PERF_TXS (${params.txTotal}) must be a multiple of PERF_WALLETS (${params.wallets}): each worker sends the same number`);
    }
    return params;
}

module.exports = { readParams, DEFAULT_SEED };
