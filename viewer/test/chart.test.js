'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const C = require('../src/lib/chart');
const { loadRecording } = require('../src/lib/load');
const { parseLines } = require('../src/lib/parse');
const { readRecordPatterns } = require('../src/lib/format');
const { stretchTable } = require('../src/lib/timeline');
const { placeWindows, tremorSpans } = require('../src/lib/windows');
const { HASH: H, BOOT_A } = require('./helpers/synthetic');
const { SYNTHETIC } = require('./helpers/paths');

const MINUS = '−';
const near = (a, b) => Math.abs(a - b) < 1e-9;
const bootA = () => loadRecording(SYNTHETIC).boots.find((b) => b.id === BOOT_A);

/** The placed window at n: its span runs from n to n + 4 and its cell from n + 3. */
const windowAt = (n) => ({ stretch: 0, window: n, code: 1, startS: n, endS: n + 4, cellStartS: n + 3 });

test('case 1 of feature 15: formatValue()', () => {
  const cases = [
    [[0], '0'],
    [[12.4], '12'],
    [[12.5], '13'],
    [[-12.6], `${MINUS}13`],
    [[1234.4], '1,234'],
    [[-1023.96875], `${MINUS}1,024`],
    [[-0.4], '0'],
    [[1234567], '1,234,567'],
    [[-0.25, 2], `${MINUS}0.25`],
    [[0.5, 1], '0.5'],
    [[1500.25, 1], '1,500.3'],
    [[-0.04, 1], '0.0'],
  ];
  for (const [args, want] of cases) {
    const got = C.formatValue(...args);
    assert.equal(got, want, args.join(', '));
    assert.ok(!got.includes('-'), `${got} holds a hyphen`);
  }
});

test('case 2 of feature 15: decimalsFor(), formatClock(), and timeLabel()', () => {
  assert.deepEqual([5, 1, 0.5, 0.1, 0.05, 0.01].map(C.decimalsFor), [0, 0, 1, 1, 2, 2]);
  assert.equal(C.formatClock(0, 0), '0:00:00');
  assert.equal(C.formatClock(5, 0), '0:00:05');
  assert.equal(C.formatClock(3723.46, 1), '1:02:03.5');
  assert.equal(C.formatClock(59.96, 1), '0:01:00.0');
  assert.equal(C.formatClock(59.6, 0), '0:01:00');
  assert.equal(C.formatClock(7200, 0), '2:00:00');
  assert.equal(C.timeLabel(30.25, 0.05), '0:00:30.25');
  assert.equal(C.timeLabel(30.25, 0.5), '0:00:30.3');
  assert.equal(C.timeLabel(90, 30), '0:01:30');
});

test('case 3 of feature 15: timeTicks()', () => {
  const a = C.timeTicks(0, 30, 900);
  assert.equal(a.step, 5);
  assert.deepEqual(a.ticks.map((t) => t.value), [0, 5, 10, 15, 20, 25, 30]);
  assert.deepEqual(
    a.ticks.map((t) => t.label),
    ['0:00:00', '0:00:05', '0:00:10', '0:00:15', '0:00:20', '0:00:25', '0:00:30'],
  );

  const b = C.timeTicks(0, 7200, 1300);
  assert.equal(b.step, 600);
  assert.equal(b.ticks.length, 13);
  assert.equal(b.ticks[12].label, '2:00:00');

  const c = C.timeTicks(100.2, 101, 900);
  assert.equal(c.step, 0.1);
  assert.equal(c.ticks.length, 9);
  c.ticks.forEach((t, i) => assert.ok(near(t.value, 100.2 + i * 0.1), `tick ${i} is ${t.value}`));
  assert.equal(c.ticks[0].label, '0:01:40.2');
  assert.equal(c.ticks[8].label, '0:01:41.0');

  const d = C.timeTicks(0, 86400, 900);
  assert.equal(d.step, 10800);
  assert.equal(d.ticks.length, 9);
});

test('case 4 of feature 15: xAt()', () => {
  assert.equal(C.xAt(5, { min: 0, max: 10 }, 1000), 500);
  assert.equal(C.xAt(2.5, { min: 0, max: 10 }, 1000), 250);
});

test('case 5 of feature 15: answerAt(), answerText(), and answerName()', () => {
  const { boots } = parseLines(
    [`B,1,11,12,${H}`, 'S,0,0,250000,114330200,1024', 'W,0,5,0,0.5,10,5', 'W,0,6,2,0.5,10,5'],
    readRecordPatterns(),
  );
  const { placed } = placeWindows(boots[0], stretchTable(boots[0]));
  assert.deepEqual(placed.map((w) => w.cellStartS), [8.25, 9.25]);
  const windowOf = (t) => C.answerAt(placed, t)?.window ?? null;
  assert.equal(windowOf(8.25), 5);
  assert.equal(windowOf(9.2499), 5);
  assert.equal(windowOf(9.25), 6);
  assert.equal(windowOf(8.2), null);
  assert.equal(windowOf(10.25), null);
  assert.equal(C.answerAt([], 8.25), null);
  assert.equal(C.answerText(placed, 8.5), 'Tremor');
  assert.equal(C.answerText(placed, 9.5), 'Arm moving');
  assert.equal(C.answerText(placed, 11), 'No answer yet');
  assert.deepEqual([0, 1, 2, 3].map(C.answerName), ['Tremor', 'No tremor', 'Arm moving', 'Warming up']);

  const boot = bootA();
  assert.equal(boot.windows.length, 151);
  for (const w of boot.windows) {
    assert.equal(C.answerAt(boot.windows, w.cellStartS + 0.5), w, `window ${w.window} of stretch ${w.stretch}`);
  }
});

test('case 6 of feature 15: the 4 second span', () => {
  for (const placed of bootA().windows) {
    assert.ok(near(placed.endS - placed.startS, 4), `window ${placed.window} of stretch ${placed.stretch}`);
  }
});

test('case 8 of feature 15: panView()', () => {
  const bounds = { min: 0, max: 100 };
  assert.deepEqual(C.panView({ min: 10, max: 20 }, bounds, 1), { min: 15, max: 25 });
  assert.deepEqual(C.panView({ min: 10, max: 20 }, bounds, -1), { min: 5, max: 15 });
  assert.deepEqual(C.panView({ min: 0, max: 10 }, bounds, -1), { min: 0, max: 10 });
  assert.deepEqual(C.panView({ min: 95, max: 100 }, bounds, 1), { min: 95, max: 100 });
  assert.deepEqual(C.panView({ min: 0, max: 100 }, bounds, 1), { min: 0, max: 100 });
});

test('case 9 of feature 15: toggleAxis()', () => {
  assert.deepEqual(C.toggleAxis(['x', 'y', 'z'], 'y'), ['x', 'z']);
  assert.deepEqual(C.toggleAxis(['x', 'z'], 'y'), ['x', 'y', 'z']);
  assert.deepEqual(C.toggleAxis(['x'], 'x'), ['x']);
});

/** True when two arrays of numbers have the same length and each pair is within 1e-9. */
const nearAll = (a, b) => a.length === b.length && a.every((v, i) => near(v, b[i]));

test('case 19 of feature 15: edgesInView()', () => {
  const spans = bootA().tremorSpans;
  const cases = [
    [{ min: 0.25, max: 160.34 }, [30.25, 60.25, 130.329262, 145.329262]],
    [{ min: 40, max: 140 }, [60.25, 130.329262]],
    [{ min: 60.25, max: 70 }, [60.25]],
    [{ min: 61, max: 130 }, []],
  ];
  for (const [view, want] of cases) {
    const got = C.edgesInView(spans, view);
    assert.ok(nearAll(got, want), `${JSON.stringify(view)} gives ${JSON.stringify(got)}`);
  }
  assert.deepEqual(C.edgesInView([], { min: 0, max: 10 }), []);
  const tremorAt = (n) => ({ ...windowAt(n), code: 0 });
  const spansOf = tremorSpans([0, 1, 2, 10].map(tremorAt));
  assert.deepEqual(C.edgesInView(spansOf, { min: 0, max: 20 }), [0, 6, 10, 14]);
});

test('case 20 of feature 15: paddedRange() and sharedRange()', () => {
  const RANGE_A = [-165.3109375, 165.3421875];
  const check = (got, want, what) => assert.ok(nearAll(got, want), `${what} gives ${JSON.stringify(got)}`);
  check(C.paddedRange(4, 4), [3, 5], 'paddedRange(4, 4)');
  check(C.paddedRange(null, 3), [-1, 1], 'paddedRange(null, 3)');
  check(C.paddedRange(-150.28125, 150.3125), RANGE_A, 'paddedRange() of boot A');
  const columns = [
    [0, 5, -3],
    [2, 10, 1],
  ];
  check(C.sharedRange(columns, 0, 2), [-3.65, 10.65], 'sharedRange(columns, 0, 2)');
  check(C.sharedRange(columns, 0, 1), [-0.5, 10.5], 'sharedRange(columns, 0, 1)');
  check(C.sharedRange(columns, null, null), [-1, 1], 'sharedRange(columns, null, null)');
  check(C.sharedRange(columns, 2, 1), [-1, 1], 'sharedRange(columns, 2, 1)');
  check(C.sharedRange([[0, 5, -3]], 0, 2), [-3.4, 5.4], 'sharedRange of one column');
  check(C.sharedRange([], 0, 2), [-1, 1], 'sharedRange([], 0, 2)');
  const b = bootA();
  const last = b.timeS.length - 1;
  check(C.sharedRange([b.gx, b.gy, b.gz], 0, last), RANGE_A, 'sharedRange() of boot A');
  check(C.sharedRange([b.gy], 0, last), [-66.3421875, 66.3109375], 'sharedRange() of boot A gy');
  check(C.sharedRange([b.gz], 0, last), [-0.34375, 0.34375], 'sharedRange() of boot A gz');
});

test('case 21 of feature 15: LINES', () => {
  assert.deepEqual(C.LINES, { tremor: { token: 'ink', widthPx: 2 } });
});

test('case 25 of feature 15: clampView()', () => {
  const bounds = { min: 0, max: 100 };
  assert.deepEqual(C.clampView(40, 10, bounds), { min: 40, max: 50 });
  assert.deepEqual(C.clampView(-5, 10, bounds), { min: 0, max: 10 });
  assert.deepEqual(C.clampView(95, 10, bounds), { min: 90, max: 100 });
  assert.deepEqual(C.clampView(20, 120, bounds), { min: 0, max: 100 });
});
