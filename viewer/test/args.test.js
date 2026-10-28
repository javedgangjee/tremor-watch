'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { parseArgs } = require('../src/lib/args');
const { ArgsError } = require('../src/lib/errors');

test('case 23: the command line', () => {
  assert.deepEqual(parseArgs(['a.gz'], '/x'), { file: '/x/a.gz', capture: null, bootId: null, recordFor: null });
  assert.deepEqual(parseArgs(['--capture', 'o.png', '--boot', '5', '/abs/a.gz'], '/x'), {
    file: '/abs/a.gz',
    capture: '/x/o.png',
    bootId: 5,
    recordFor: null,
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
