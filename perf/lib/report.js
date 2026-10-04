'use strict';
// Reads the summary table Caliper prints at the end of a run ("### All test results ###") into numbers,
// so a result is a file and not a copy from a terminal. Anything that is not exactly one round is refused:
// a failed run must never be read as zero.

const ROW = /^\|\s*([^|\s][^|]*?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*$/;

function parseSummary(text) {
    const marker = '### All test results ###';
    const at = text.lastIndexOf(marker);
    if (at < 0) {
        throw new Error('no results table in the Caliper output');
    }
    const rows = text.slice(at).split(/\r?\n/).map((line) => line.replace(/^.*?(\|)/, '$1')).map((line) => ROW.exec(line)).filter(Boolean);
    if (rows.length === 0) {
        throw new Error('no results table in the Caliper output');
    }
    if (rows.length > 1) {
        throw new Error(`expected one round in the results table, found ${rows.length}`);
    }
    const [, label, succ, fail, rate, max, min, avg, tput] = rows[0];
    return {
        label,
        succeeded: Number(succ),
        failed: Number(fail),
        sendRateTps: Number(rate),
        maxLatencyS: Number(max),
        minLatencyS: Number(min),
        avgLatencyS: Number(avg),
        throughputTps: Number(tput),
    };
}

module.exports = { parseSummary };
