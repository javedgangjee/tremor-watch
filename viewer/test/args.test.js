'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { parseArgs, captureSelect } = require('../src/lib/args');
const { ArgsError } = require('../src/lib/errors');

test('case 23: the command line', () => {
  assert.deepEqual(parseArgs(['a.gz'], '/x'), {
    file: '/x/a.gz',
    capture: null,
    bootId: null,
    recordFor: null,
    theme: 'system',
    layout: 'overlaid',
  });
  assert.deepEqual(parseArgs(['--capture', 'o.png', '--boot', '5', '/abs/a.gz'], '/x'), {
    file: '/abs/a.gz',
    capture: '/x/o.png',
    bootId: 5,
    recordFor: null,
    theme: 'system',
    layout: 'overlaid',
  });
  assert.equal(parseArgs([], '/x').file, null);
  for (const argv of [['--frob'], ['--capture'], ['a', 'b'], ['--boot', 'x']]) {
    assert.throws(() => parseArgs(argv, '/x'), ArgsError, argv.join(' '));
  }
});

test('case 13 of feature 14: --record-for', () => {
  assert.deepEqual(parseArgs(['--record-for', '60', '--capture', 'o.png'], '/x'), {
    file: null,
    capture: '/x/o.png',
    bootId: null,
    recordFor: 60,
    theme: 'system',
    layout: 'overlaid',
  });
  for (const argv of [
    ['--record-for', '60'],
    ['--record-for', '60', '--capture', 'o.png', 'a.gz'],
    ['--record-for', '0', '--capture', 'o.png'],
    ['--record-for', '1.5', '--capture', 'o.png'],
    ['--record-for', '86401', '--capture', 'o.png'],
  ]) {
    assert.throws(() => parseArgs(argv, '/x'), ArgsError, argv.join(' '));
  }
});

test('case 12 of feature 15: --theme and --layout', () => {
  assert.deepEqual(parseArgs(['a.gz', '--theme', 'dark', '--layout', 'stacked'], '/x'), {
    file: '/x/a.gz',
    capture: null,
    bootId: null,
    recordFor: null,
    theme: 'dark',
    layout: 'stacked',
  });
  const plain = parseArgs(['a.gz'], '/x');
  assert.equal(plain.theme, 'system');
  assert.equal(plain.layout, 'overlaid');
  for (const argv of [['--theme', 'blue'], ['--layout', 'grid'], ['a.gz', '--theme']]) {
    assert.throws(() => parseArgs(argv, '/x'), ArgsError, argv.join(' '));
  }
});

test('case 23 of feature 15: TREMOR_CAPTURE_SELECT', () => {
  assert.deepEqual(captureSelect({ TREMOR_CAPTURE_SELECT: '0,105' }), { stretch: 0, window: 105 });
  assert.equal(captureSelect({}), null);
  for (const text of ['', 'a,1', '1', '1,2,3', '-1,2', '0,1.5']) {
    assert.throws(() => captureSelect({ TREMOR_CAPTURE_SELECT: text }), ArgsError, JSON.stringify(text));
  }
});
