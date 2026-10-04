'use strict';
// The configuration a round was measured under, saved with its numbers (plan anti-gate: no numbers
// without their configuration). Both layers get the same snapshot apart from `layer` and the time.

function readGenesisSettings(genesis) {
    const period = genesis && genesis.config && genesis.config.qbft && genesis.config.qbft.blockperiodseconds;
    if (!period) {
        throw new Error('the genesis has no QBFT block period');
    }
    if (!genesis.gasLimit) {
        throw new Error('the genesis has no gas limit');
    }
    return {
        blockPeriodSeconds: period,
        gasLimit: genesis.gasLimit,
        gasLimitDecimal: BigInt(genesis.gasLimit).toString(),
    };
}

function buildSnapshot({ layer, params, genesis, topology, versions, now = new Date() }) {
    return {
        layer,
        generatedAt: now.toISOString(),
        load: {
            workers: params.wallets,
            offeredTpsTotal: params.tpsTotal,
            offeredTpsPerWorker: params.tpsTotal / params.wallets,
            transactions: params.txTotal,
            amount: params.amount,
        },
        chain: readGenesisSettings(genesis),
        topology,
        versions,
    };
}

module.exports = { buildSnapshot, readGenesisSettings };
