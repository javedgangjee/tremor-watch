'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { parseLines } = require('../src/lib/parse');
const { readRecordPatterns } = require('../src/lib/format');
const { HASH: H } = require('./helpers/synthetic');

const patterns = readRecordPatterns();
const parse = (lines) => parseLines(lines, patterns);

test('case 4: the skip rules leave one boot with one burst', () => {
  const { boots, counts } = parse([
    'ESP-ROM:esp32s3-20210327',
    'T,500,11,123',
    'R,500,1,2,3,4,5,6',
    `B,1,11,12,${H}`,
    'S,0,0,1000,0,1024',
    'T,0,2,1000',
    'R,0,32,-32,64,0,0,4096',
    'R,1,0,0,0,0,0,4096',
    'START uptime_us=1',
    '> TONE,0',
    'A,4,0',
    'F,0,1',
    'D,5,',
  ]);
  assert.equal(boots.length, 1);
  assert.equal(boots[0].id, 1);
  assert.equal(boots[0].firmware, 12);
  assert.equal(boots[0].bursts.length, 1);
  assert.equal(boots[0].bursts[0].count, 2);
  assert.deepEqual([...boots[0].bursts[0].gyro], [32, -32, 64, 0, 0, 0]);
  assert.equal(counts.bad, 0);
  assert.equal(counts.droppedBursts, 0);
});

test('case 5: bursts that break their order or fall short', () => {
  const head = [`B,1,11,12,${H}`, 'T,0,3,1000'];
  const r = (n) => `R,${n},1,2,3,0,0,4096`;

  let parsed = parse([...head, r(0), r(2), r(1)]);
  assert.equal(parsed.counts.droppedBursts, 1);
  assert.equal(parsed.boots[0].bursts.length, 0);

  parsed = parse([...head, r(0), r(1), 'T,3,1,2000', r(3)]);
  assert.equal(parsed.counts.droppedBursts, 1);
  assert.deepEqual(parsed.boots[0].bursts.map((b) => b.first), [3]);

  parsed = parse([...head, r(0), r(1)]);
  assert.equal(parsed.counts.droppedBursts, 0);
  assert.equal(parsed.boots[0].bursts.length, 0);
});

test('case 6: each bad line counts once and adds nothing', () => {
  const { boots, counts } = parse([
    `B,1,11,12,${H}`,
    'R,1234,5',
    'T,0,0,1000',
    'T,0,257,1000',
    'R,0,32768,0,0,0,0,0',
    'W,0,5,0,1.2.3,1,1',
    'S,0,99999999999999999999,0,0,1024',
  ]);
  assert.equal(counts.bad, 6);
  assert.equal(boots[0].bursts.length, 0);
  assert.equal(boots[0].sLines.size, 0);
  assert.equal(boots[0].windows.size, 0);
});

test('case 7: repeated B lines, the last S line, faults, and the last W line', () => {
  const { boots } = parse([
    `B,1,11,12,${H}`,
    'S,0,0,1000,0,1024',
    `B,1,11,12,${H}`,
    'S,0,0,1000,114330200,1024',
    'W,0,,4,,,',
    'W,0,5,0,0.5,10,5',
    'W,0,5,1,0.5,10,5',
    `B,2,11,12,${H}`,
  ]);
  assert.deepEqual(boots.map((b) => b.id), [1, 2]);
  assert.equal(boots[0].sLines.get(0).rateUhz, 114330200);
  assert.equal(boots[0].faults, 1);
  assert.equal(boots[0].windows.size, 1);
  assert.equal(boots[0].windows.get('0,5').code, 1);
});
