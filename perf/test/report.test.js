'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { parseSummary } = require('../lib/report');

const TABLE = `
2026.10.04-15:13:37.566 info  [caliper] [report-builder] 	### All test results ###
2026.10.04-15:13:37.566 info  [caliper] [report-builder] 	
+------------+------+------+-----------------+-----------------+-----------------+-----------------+------------------+
| Name       | Succ | Fail | Send Rate (TPS) | Max Latency (s) | Min Latency (s) | Avg Latency (s) | Throughput (TPS) |
|------------|------|------|-----------------|-----------------|-----------------|-----------------|------------------|
| transfer   | 598  | 2    | 19.8            | 4.10            | 0.55            | 2.31            | 17.9             |
+------------+------+------+-----------------+-----------------+-----------------+-----------------+------------------+
`;

test('reads the summary row of the last results table', () => {
    assert.deepStrictEqual(parseSummary(TABLE), {
        label: 'transfer',
        succeeded: 598,
        failed: 2,
        sendRateTps: 19.8,
        maxLatencyS: 4.1,
        minLatencyS: 0.55,
        avgLatencyS: 2.31,
        throughputTps: 17.9,
    });
});

test('uses the final table when the summary is printed twice (per round and in all)', () => {
    const first = TABLE.replace('| 598 ', '| 1   ');
    assert.strictEqual(parseSummary(first + TABLE).succeeded, 598);
});

test('refuses output with no results table, so a failed run is never read as zero', () => {
    assert.throws(() => parseSummary('Benchmark failed'), /no results table/);
});

test('refuses a table with more than one round', () => {
    const row = '| other      | 1    | 0    | 1.0             | 1.00            | 1.00            | 1.00            | 1.0              |';
    const two = TABLE.replace(/(\| transfer .*\n)/, `$1${row}\n`);
    assert.throws(() => parseSummary(two), /one round/);
});
