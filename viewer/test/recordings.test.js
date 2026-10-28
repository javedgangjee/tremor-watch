'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const zlib = require('node:zlib');
const test = require('node:test');
const { loadRecording } = require('../src/lib/load');
const { SYNTHETIC, log } = require('./helpers/paths');
const { readingAt } = require('./helpers/readings');

const LOGS = ['record_log', 'command_log', 'drop_log', 'face_log'];
const loaded = new Map(LOGS.map((name) => [name, loadRecording(log(name))]));
const bootOf = (name, id) => loaded.get(name).boots.find((b) => b.id === id);

const breakReadings = (boot) => boot.breaks.map((i) => readingAt(boot, i));
const byCode = (boot) => boot.counts.windowsByCode;

test('case 15: record_log.txt.gz', () => {
  const recording = loaded.get('record_log');
  assert.equal(recording.cutShort, false);
  assert.equal(recording.counts.bad, 0);
  assert.equal(recording.counts.droppedBursts, 0);
  assert.equal(recording.boots.length, 1);
  const boot = recording.boots[0];
  assert.equal(boot.id, 2274443476);
  assert.equal(boot.firmware, 9);
  assert.equal(boot.resetCause, 11);
  assert.deepEqual(boot.stretches, [{ number: 0, first: 0, t0Us: 234273, rateUhz: 114347777, estimated: false }]);
  assert.equal(boot.counts.readings, 206041);
  assert.deepEqual(boot.breaks, []);
  assert.equal(boot.timeS[206040], (234273 + (206040 * 1e12) / 114347777) / 1e6);
  assert.equal(boot.windows.length, 1798);
  assert.deepEqual(byCode(boot).slice(0, 4), [0, 1797, 0, 1]);
  assert.deepEqual(boot.tremorSpans, []);
});

test('case 16: command_log.txt.gz', () => {
  const first = bootOf('command_log', 3162426297);
  assert.equal(first.counts.readings, 1166);
  assert.equal(first.windows.length, 7);
  assert.deepEqual(byCode(first).slice(0, 4), [0, 6, 0, 1]);

  const boot = bootOf('command_log', 505078862);
  assert.equal(boot.counts.readings, 144078);
  assert.deepEqual(
    boot.stretches.map(({ number, first: f, t0Us, rateUhz }) => [number, f, t0Us, rateUhz]),
    [
      [0, 0, 234313, 114348497],
      [1, 108185, 946328952, 114349025],
    ],
  );
  assert.deepEqual(breakReadings(boot), [108185]);
  assert.equal(boot.windows.length, 1252);
  assert.deepEqual(byCode(boot).slice(0, 4), [0, 1250, 0, 2]);
});

test('case 17: drop_log.txt.gz', () => {
  const recording = loaded.get('drop_log');
  assert.equal(recording.counts.droppedBursts, 2);
  assert.equal(recording.boots.length, 1);
  const boot = bootOf('drop_log', 3492590314);
  assert.equal(boot.counts.readings, 25256);
  assert.deepEqual(breakReadings(boot), [8052, 14883]);
  assert.equal(boot.windows.length, 216);
  assert.ok(boot.windows.every((w) => w.stretch === 0));
  const highest = boot.windows.reduce((a, b) => (b.window > a.window ? b : a));
  assert.equal(highest.window, 276);
  assert.equal(highest.startS, (234278 + 276 * 1e6) / 1e6);
});

test('case 18: face_log.txt.gz', () => {
  const recording = loaded.get('face_log');
  assert.equal(recording.boots.length, 1);
  const boot = recording.boots[0];
  assert.equal(boot.id, 2694533211);
  assert.equal(boot.firmware, 11);
  assert.equal(boot.counts.readings, 130526);
  assert.equal(boot.windows.length, 1138);
  assert.deepEqual(byCode(boot).slice(0, 4), [0, 1137, 0, 1]);
});

/** The tremor W lines found by a plain text scan, as "boot,stretch,window". */
function scanTremorKeys(filePath) {
  const keys = new Set();
  let bootId = null;
  for (const raw of zlib.gunzipSync(fs.readFileSync(filePath)).toString('utf8').split('\n')) {
    const line = raw.replace(/^[0-9.]+\t/, '');
    const b = /^B,(\d+),/.exec(line);
    if (b) {
      bootId = b[1];
    }
    const w = /^W,(\d+),(\d+),0,/.exec(line);
    if (w && bootId !== null) {
      keys.add(`${bootId},${w[1]},${w[2]}`);
    }
  }
  return keys;
}

test('case 19: the placed tremor windows match a plain scan', () => {
  const files = [...LOGS.map((name) => [log(name), loaded.get(name)]), [SYNTHETIC, loadRecording(SYNTHETIC)]];
  for (const [filePath, recording] of files) {
    const placed = new Set();
    for (const boot of recording.boots) {
      for (const w of boot.windows.filter((x) => x.code === 0)) {
        placed.add(`${boot.id},${w.stretch},${w.window}`);
      }
    }
    assert.deepEqual(placed, scanTremorKeys(filePath), filePath);
    assert.equal(placed.size, filePath === SYNTHETIC ? 39 : 0, filePath);
  }
});
