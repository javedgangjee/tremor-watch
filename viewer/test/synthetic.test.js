'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const test = require('node:test');
const { loadRecording } = require('../src/lib/load');
const { buildSyntheticText, BOOT_A, BOOT_B, T1_US, RATE_UHZ } = require('./helpers/synthetic');
const { SYNTHETIC } = require('./helpers/paths');
const { tempFolder } = require('./helpers/temp');
const { readingAt } = require('./helpers/readings');

const near = (a, b) => Math.abs(a - b) < 1e-9;

test('case 20: the committed made-up recording matches its generator', () => {
  assert.ok(zlib.gunzipSync(fs.readFileSync(SYNTHETIC)).equals(Buffer.from(buildSyntheticText(), 'utf8')));
});

test('case 21: the made-up recording loads as validation.md describes', () => {
  const recording = loadRecording(SYNTHETIC);
  assert.equal(recording.cutShort, false);
  assert.equal(recording.counts.bad, 1);
  assert.equal(recording.counts.droppedBursts, 1);
  assert.deepEqual(recording.boots.map((b) => b.id), [BOOT_A, BOOT_B]);

  const [a, b] = recording.boots;
  assert.equal(a.counts.readings, 18260);
  assert.deepEqual(a.stretches, [
    { number: 0, first: 0, t0Us: 250000, rateUhz: 114330200, estimated: false },
    { number: 1, first: 13728, t0Us: T1_US, rateUhz: 114331000, estimated: false },
  ]);
  assert.deepEqual(a.breaks.map((i) => readingAt(a, i)), [8019, 11473, 13728]);
  assert.equal(a.windows.length, 151);
  assert.deepEqual(a.counts.windowsByCode.slice(0, 4), [39, 92, 18, 2]);
  assert.equal(a.counts.faults, 1);
  assert.equal(a.counts.notPlaced, 0);
  assert.ok(!a.windows.some((w) => w.stretch === 0 && w.window === 96));
  assert.equal(a.tremorSpans.length, 2);
  assert.deepEqual(a.tremorSpans[0], [30.25, 60.25]);
  assert.ok(near(a.tremorSpans[1][0], T1_US / 1e6 + 10));
  assert.ok(near(a.tremorSpans[1][1], T1_US / 1e6 + 25));

  assert.equal(b.counts.readings, 913);
  assert.equal(b.stretches.length, 1);
  assert.equal(b.stretches[0].estimated, true);
  assert.ok(Math.abs(b.stretches[0].rateUhz - RATE_UHZ) <= 115);
  assert.equal(b.counts.faults, 1);
  assert.equal(b.windows.length, 0);
});

test('case 22: a copy cut short loads up to the cut', () => {
  const bytes = fs.readFileSync(SYNTHETIC);
  const cut = path.join(tempFolder(), 'cut.txt.gz');
  fs.writeFileSync(cut, bytes.subarray(0, Math.floor(bytes.length * 0.6)));
  const recording = loadRecording(cut);
  assert.equal(recording.cutShort, true);
  assert.ok(recording.boots[0].counts.readings < 18260);
});
