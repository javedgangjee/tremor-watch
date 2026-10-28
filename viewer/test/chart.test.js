'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const C = require('../src/lib/chart');
const { loadRecording } = require('../src/lib/load');
const { parseLines } = require('../src/lib/parse');
const { readRecordPatterns } = require('../src/lib/format');
const { stretchTable } = require('../src/lib/timeline');
const { placeWindows } = require('../src/lib/windows');
const { HASH: H, BOOT_A } = require('./helpers/synthetic');
const { SYNTHETIC } = require('./helpers/paths');

const MINUS = '−';
const near = (a, b) => Math.abs(a - b) < 1e-9;
const bootA = () => loadRecording(SYNTHETIC).boots.find((b) => b.id === BOOT_A);

/** The placed window at n: its span runs from n to n + 4 and its cell from n + 3. */
const windowAt = (n) => ({ stretch: 0, window: n, code: 1, startS: n, endS: n + 4, cellStartS: n + 3 });
const windows0to9 = () => Array.from({ length: 10 }, (_, n) => windowAt(n));

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

test('case 4 of feature 15: xAt(), timeAt(), and blockLayout()', () => {
  const view = { min: 0, max: 10 };
  assert.equal(C.xAt(5, view, 1000), 500);
  assert.equal(C.timeAt(250, view, 1000), 2.5);
  const cell = (start) => ({ cellStartS: start });
  assert.deepEqual(C.blockLayout(cell(3), view, 1000), { x: 300, width: 98, joined: false });
  assert.deepEqual(C.blockLayout(cell(9.5), view, 1000), { x: 950, width: 50, joined: false });
  assert.deepEqual(C.blockLayout(cell(-0.5), view, 1000), { x: 0, width: 48, joined: false });
  assert.equal(C.blockLayout(cell(10), view, 1000), null);
  assert.equal(C.blockLayout(cell(-1), view, 1000), null);
  assert.deepEqual(C.blockLayout(cell(100), { min: 0, max: 250 }, 1000), { x: 400, width: 2, joined: false });
  assert.deepEqual(C.blockLayout(cell(3600), { min: 0, max: 7200 }, 1300), { x: 650, width: 1, joined: true });
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

test('case 6 of feature 15: windowText() and the 4 second span', () => {
  const w = { stretch: 0, window: 5, code: 0, startS: 5.25, endS: 9.25, cellStartS: 8.25 };
  assert.equal(C.windowText(w), 'Window 5 of stretch 0: tremor, from 0:00:05.3 to 0:00:09.3');
  for (const placed of bootA().windows) {
    assert.ok(near(placed.endS - placed.startS, 4), `window ${placed.window} of stretch ${placed.stretch}`);
  }
});

test('case 7 of feature 15: stepSelection()', () => {
  const ws = windows0to9();
  const view = { min: 5, max: 8 };
  const step = (index, key) => C.stepSelection(ws, index, key, view);
  assert.equal(step(null, 'ArrowRight'), 2);
  assert.equal(step(null, 'ArrowLeft'), 4);
  assert.equal(step(3, 'ArrowRight'), 4);
  assert.equal(step(9, 'ArrowRight'), 9);
  assert.equal(step(0, 'ArrowLeft'), 0);
  assert.equal(step(3, 'Home'), 0);
  assert.equal(step(3, 'End'), 9);
  assert.equal(step(3, 'Escape'), null);
  assert.equal(step(3, 'a'), 3);
  assert.equal(C.stepSelection([], null, 'ArrowRight', view), null);
});

test('case 8 of feature 15: keepInView() and panView()', () => {
  const bounds = { min: 0, max: 100 };
  const ten = { min: 0, max: 10 };
  assert.deepEqual(C.keepInView(ten, bounds, 3, 4), { min: 0, max: 10 });
  assert.deepEqual(C.keepInView(ten, bounds, 50, 51), { min: 45.5, max: 55.5 });
  assert.deepEqual(C.keepInView(ten, bounds, 99, 100), { min: 90, max: 100 });
  assert.deepEqual(C.keepInView({ min: 20, max: 30 }, bounds, 1, 2), { min: 0, max: 10 });
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
