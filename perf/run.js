'use strict';
// Runs one round and saves its numbers with the configuration they were measured under.
//   node run.js chain|firefly      (npm run round:chain, npm run round:firefly)
// Checks that the wallets are set up, runs Caliper, reads its summary table, checks that the transfers
// only moved COIN (the sum of the wallets' balances is the same before and after), and writes
// results/<layer>.json. Exits non-zero if a transaction failed or the sum changed.
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { prepare } = require('./lib/prepare');
const { readParams } = require('./lib/params');
const { deriveAddresses } = require('./lib/wallets');
const { parseSummary } = require('./lib/report');
const { buildSnapshot } = require('./lib/snapshot');

const root = path.resolve(__dirname, '..');
const FIREFLY = process.env.FIREFLY_URL || 'http://localhost:5000';
const NS = `${FIREFLY}/api/v1/namespaces/default`;

// Each layer has its own set of wallets: the chain layer uses wallets 0 to N-1, the FireFly layer N to 2N-1.
const LAYERS = {
    chain: { network: 'generated/ethereum.json', benchmark: 'generated/benchmark-chain.yaml', offset: (params) => 0 },
    firefly: { network: 'generated/firefly.json', benchmark: 'generated/benchmark-firefly.yaml', offset: (params) => params.wallets }
};

async function post(pathname, body) {
    const response = await fetch(`${NS}${pathname}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    if (!response.ok) {
        throw new Error(`FireFly ${pathname} answered ${response.status}: ${await response.text()}`);
    }
    return response.json();
}

async function balances(addresses) {
    const result = {};
    for (const address of addresses) {
        const answer = await post('/apis/coin/query/balanceOf', { input: { _userAddress: address } });
        result[address] = BigInt(answer.output);
    }
    return result;
}

async function checkWallets(params, addresses) {
    const needed = BigInt(params.amount) * BigInt(params.txTotal / params.wallets);
    const held = await balances(addresses);
    for (const address of addresses) {
        const verified = (await post('/apis/identity-registry/query/isVerified', { input: { _userAddress: address } })).output;
        if (verified !== true || held[address] < needed) {
            throw new Error(
                `wallet ${address} is not ready (verified: ${verified}, balance: ${held[address]}, needs ${needed}). ` +
                `Run: python scripts/stack.py perf-setup --wallets ${params.wallets} (it prepares ${2 * params.wallets}: N per layer)`
            );
        }
    }
    return held;
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// A round must start with nothing queued in FireFly: operations left over from an earlier round are still
// being sent and would take capacity from the round being measured.
async function waitForNoPendingOperations(seconds = 180) {
    const deadline = Date.now() + seconds * 1000;
    for (;;) {
        const response = await fetch(`${NS}/operations?status=Pending&limit=1`);
        const pending = await response.json();
        if (pending.length === 0) {
            return;
        }
        if (Date.now() >= deadline) {
            throw new Error(`FireFly still has pending operations after ${seconds} s. Run \`python scripts/stack.py reset\` to start clean.`);
        }
        console.log('waiting for FireFly to finish pending operations...');
        await sleep(5000);
    }
}

function sum(map) {
    return Object.values(map).reduce((a, b) => a + b, 0n);
}

function topology() {
    const keys = path.join(root, 'network-config', 'validator-keys');
    const compose = fs.readFileSync(path.join(root, 'docker-compose.yml'), 'utf8');
    return {
        validators: fs.readdirSync(keys).filter((name) => fs.statSync(path.join(keys, name)).isDirectory()).length,
        rpcNodes: (compose.match(/container_name: besu-rpc-/g) || []).length
    };
}

function versions() {
    const compose = fs.readFileSync(path.join(root, 'docker-compose.yml'), 'utf8');
    const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8'));
    const firefly = /ghcr\.io\/hyperledger-firefly\/firefly@(sha256:[0-9a-f]{12})/.exec(compose);
    return {
        besu: (/hyperledger\/besu:[\w.-]+/.exec(compose) || ['unknown'])[0],
        fireflyCore: firefly ? `${firefly[1]}…` : 'unknown',
        caliper: pkg.dependencies['@hyperledger/caliper-cli'],
        node: process.version
    };
}

function runCaliper(layerConfig, reportPath) {
    const caliper = path.join(__dirname, 'node_modules', '@hyperledger', 'caliper-cli', 'caliper.js');
    const args = [
        caliper, 'launch', 'manager',
        '--caliper-workspace', '.',
        '--caliper-benchconfig', layerConfig.benchmark,
        '--caliper-networkconfig', layerConfig.network,
        '--caliper-report-path', reportPath,
        '--caliper-flow-skip-start', '--caliper-flow-skip-install', '--caliper-flow-skip-end'
    ];
    return new Promise((resolve, reject) => {
        const child = spawn(process.execPath, args, { cwd: __dirname });
        let output = '';
        const take = (chunk) => {
            output += chunk;
            process.stdout.write(chunk);
        };
        child.stdout.on('data', take);
        child.stderr.on('data', take);
        child.on('error', reject);
        child.on('close', (code) => resolve({ code, output }));
    });
}

async function main() {
    const layer = process.argv[2];
    if (!LAYERS[layer]) {
        throw new Error(`usage: node run.js <${Object.keys(LAYERS).join('|')}>`);
    }
    const params = readParams();
    prepare(params);
    await waitForNoPendingOperations();
    const offset = LAYERS[layer].offset(params);
    const addresses = deriveAddresses(params.seed, offset + params.wallets).slice(offset);
    const before = await checkWallets(params, addresses);

    const reportPath = `results/${layer}-report.html`;
    fs.mkdirSync(path.join(__dirname, 'results'), { recursive: true });
    const { code, output } = await runCaliper(LAYERS[layer], reportPath);
    if (code !== 0) {
        throw new Error(`Caliper exited with ${code}`);
    }
    const summary = parseSummary(output);
    const after = await balances(addresses);
    const genesis = JSON.parse(fs.readFileSync(path.join(root, 'network-config', 'genesis.json'), 'utf8'));
    const snapshot = buildSnapshot({ layer, params, genesis, topology: topology(), versions: versions() });
    const result = {
        snapshot,
        summary,
        balanceSum: { before: sum(before).toString(), after: sum(after).toString() }
    };
    const file = path.join(__dirname, 'results', `${layer}.json`);
    fs.writeFileSync(file, JSON.stringify(result, null, 2));
    console.log(`\n${layer} layer: ${summary.succeeded} succeeded, ${summary.failed} failed, ` +
        `${summary.throughputTps} TPS, average latency ${summary.avgLatencyS} s. Saved ${path.relative(root, file)}`);

    if (summary.failed > 0 || summary.succeeded !== params.txTotal) {
        throw new Error(`expected ${params.txTotal} succeeded and 0 failed, got ${summary.succeeded} and ${summary.failed}`);
    }
    if (result.balanceSum.before !== result.balanceSum.after) {
        throw new Error(`the sum of the wallets' balances changed (${result.balanceSum.before} to ${result.balanceSum.after})`);
    }
}

main().catch((error) => {
    console.error(`error: ${error.message}`);
    process.exit(1);
});
