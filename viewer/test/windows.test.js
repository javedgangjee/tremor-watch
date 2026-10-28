'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { parseLines } = require('../src/lib/parse');
const { readRecordPatterns } = require('../src/lib/format');
const { stretchTable } = require('../src/lib/timeline');
const { placeWindows, tremorSpans } = require('../src/lib/windows');
const { HASH: H } = require('./helpers/synthetic');

const patterns = readRecordPatterns();

function placedFrom(wLines) {
  const { boots } = parseLines([`B,1,11,12,${H}`, 'S,0,0,250000,114330200,1024', ...wLines], patterns);
  return placeWindows(boots[0], stretchTable(boots[0]));
}

const windowsWithCode = (code, numbers) => numbers.map((n) => `W,0,${n},${code},0.5,10,5`);

test('case 13: windows are placed with the t0 of their stretch', () => {
  const { placed, notPlaced, faults } = placedFrom(['W,0,0,3,0.5,10,5', 'W,0,5,0,0.5,10,5', 'W,3,2,1,0.5,10,5', 'W,0,,4,,,']);
  const five = placed.find((w) => w.window === 5);
  assert.equal(five.startS, 5.25);
  assert.equal(five.endS, 9.25);
  assert.equal(five.cellStartS, 8.25);
  assert.equal(placed.length, 2);
  assert.equal(notPlaced, 1);
  assert.equal(faults, 1);
});

test('case 14: tremor spans join where they overlap or touch', () => {
  const spans = (code, numbers) => tremorSpans(placedFrom(windowsWithCode(code, numbers)).placed);
  assert.deepEqual(spans(0, [5, 6, 7]), [[5.25, 11.25]]);
  assert.deepEqual(spans(0, [5, 9]), [[5.25, 13.25]]);
  assert.deepEqual(spans(0, [5, 10]), [[5.25, 9.25], [10.25, 14.25]]);
  assert.deepEqual(spans(1, [5, 6, 7]), []);
});
