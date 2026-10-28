'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { parseLines } = require('../src/lib/parse');
const { readRecordPatterns } = require('../src/lib/format');
const { buildTimeline } = require('../src/lib/timeline');
const { HASH: H, burstStamp } = require('./helpers/synthetic');

const patterns = readRecordPatterns();
const RATE = 114330200;

/** The T line and R lines of a burst, with gyroscope counts that follow the reading number. */
function burst(first, count, stamp) {
  const lines = [`T,${first},${count},${stamp}`];
  for (let n = first; n < first + count; n++) {
    lines.push(`R,${n},${(n % 1000) * 32},${(n % 500) - 250},7,0,0,4096`);
  }
  return lines;
}

function timelineOf(lines) {
  const { boots } = parseLines([`B,1,11,12,${H}`, ...lines], patterns);
  return buildTimeline(boots[0]);
}

test('case 8: reading times and degrees per second within one stretch', () => {
  const lines = ['S,0,0,250000,114330200,1024'];
  for (let b = 0; b < 10; b++) {
    lines.push(...burst(b * 11, 11, burstStamp(b * 11, 0, 250000, RATE)));
  }
  const t = timelineOf(lines);
  assert.equal(t.timeS.length, 110);
  for (let i = 0; i < 110; i++) {
    assert.equal(t.timeS[i], (250000 + (i * 1e12) / RATE) / 1e6);
    assert.equal(t.gx[i], ((i % 1000) * 32) / 32);
    assert.equal(t.gy[i], ((i % 500) - 250) / 32);
    assert.equal(t.gz[i], 7 / 32);
  }
  assert.deepEqual(t.breaks, []);
});

test('case 9: the two hour example keeps microsecond steps', () => {
  const t = timelineOf(['S,0,0,0,114330200,1024', ...burst(823178, 2, 7200004900)]);
  assert.ok(Math.abs(t.timeS[0] - (823178 * 1e12) / RATE / 1e6) < 1e-9);
  assert.ok(Math.abs(t.timeS[0] - 7200.0049) < 1e-4);
  assert.ok(Math.abs(t.timeS[1] - t.timeS[0] - 1 / 114.3302) < 1e-9);
});

test('case 10: breaks at a gap and at a new stretch', () => {
  let t = timelineOf(['S,0,0,250000,114330200,1024', ...burst(0, 11, 250000), ...burst(22, 11, 442000)]);
  assert.deepEqual(t.breaks, [11]);
  assert.equal(t.timeS[11], (250000 + (22 * 1e12) / RATE) / 1e6);

  t = timelineOf([
    'S,0,0,250000,114330200,1024',
    ...burst(0, 11, 250000),
    'S,1,11,500000,114330200,1024',
    ...burst(11, 11, 500000),
  ]);
  assert.deepEqual(t.breaks, [11]);
  assert.equal(t.timeS[11], 0.5);
});

test('case 11: a stretch with rate 0 gets an estimated rate', () => {
  const lines = ['S,0,0,300000,0,1024'];
  for (let b = 0; b < 84; b++) {
    lines.push(...burst(b * 11, 11, 300000 + Math.floor((11 * b * 1e12) / RATE + 0.5)));
  }
  let [s] = timelineOf(lines).stretches;
  assert.equal(s.estimated, true);
  assert.ok(Math.abs(s.rateUhz - RATE) <= 115);

  [s] = timelineOf(['S,0,0,300000,0,1024', ...burst(0, 11, 300000)]).stretches;
  assert.equal(s.estimated, true);
  assert.equal(s.rateUhz, 114330200);

  const two = timelineOf([
    'S,0,0,300000,114331000,1024',
    ...burst(0, 11, 300000),
    'S,1,11,500000,0,1024',
    ...burst(11, 11, 500000),
  ]).stretches;
  assert.equal(two[1].estimated, true);
  assert.equal(two[1].rateUhz, 114331000);
});

test('case 12: readings that no S line covers are left out and counted', () => {
  const t = timelineOf(['S,0,11,250000,114330200,1024', ...burst(0, 11, 150000), ...burst(11, 11, 250000)]);
  assert.equal(t.noStretchReadings, 11);
  assert.equal(t.timeS.length, 11);
  assert.equal(t.timeS[0], 0.25);
});
