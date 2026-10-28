'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { parseArgs } = require('../src/lib/args');
const { ArgsError } = require('../src/lib/errors');

test('case 23: the command line', () => {
  assert.deepEqual(parseArgs(['a.gz'], '/x'), { file: '/x/a.gz', capture: null, bootId: null });
  assert.deepEqual(parseArgs(['--capture', 'o.png', '--boot', '5', '/abs/a.gz'], '/x'), {
    file: '/abs/a.gz',
    capture: '/x/o.png',
    bootId: 5,
  });
  assert.equal(parseArgs([], '/x').file, null);
  for (const argv of [['--frob'], ['--capture'], ['a', 'b'], ['--boot', 'x']]) {
    assert.throws(() => parseArgs(argv, '/x'), ArgsError, argv.join(' '));
  }
});
