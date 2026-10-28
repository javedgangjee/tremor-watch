'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { startText } = require('../src/lib/title');
const { loadRecording } = require('../src/lib/load');
const { HASH: H } = require('./helpers/synthetic');
const { SYNTHETIC, log } = require('./helpers/paths');
const { tempFolder } = require('./helpers/temp');

test('case 10 of feature 15: the start from the file name', () => {
  assert.equal(startText('tremor-2026-10-28-142813.txt.gz', []), 'Oct 28, 2026 at 14:28');
  assert.equal(startText('tremor-2027-01-05-090500-2.txt.gz', []), 'Jan 5, 2027 at 09:05');
  assert.equal(startText('tremor-2024-02-29-235959.txt.gz', []), 'Feb 29, 2024 at 23:59');
  for (const name of [
    'tremor-2026-13-01-000000.txt.gz',
    'tremor-2026-02-30-120000.txt.gz',
    'tremor-2025-02-29-120000.txt.gz',
    'tremor-2026-10-28-240000.txt.gz',
    'tremor-2026-10-28-126000.txt.gz',
    'tremor-2026-10-28-142813.txt',
    'xtremor-2026-10-28-142813.txt.gz',
    'record_log.txt.gz',
  ]) {
    assert.equal(startText(name, []), null, name);
  }
});

const CLOCK = '> CLOCK,1793209555689292,-240';
/** The lines L of case 11, with the CLOCK line changed to clock. */
const linesWith = (clock = CLOCK) => ['ESP-ROM:esp32s3-20210327', `B,1,11,12,${H}`, 'START uptime_us=1', clock, 'T,0,2,1000'];

test('case 11 of feature 15: the start from the CLOCK line', () => {
  assert.equal(startText('shake.txt.gz', linesWith()), 'Oct 28, 2026 at 13:45');
  assert.equal(startText('shake.txt.gz', linesWith('> CLOCK,1761206400000000,840')), 'Oct 23, 2025 at 22:00');
  assert.equal(startText('shake.txt.gz', linesWith('> CLOCK,1767225599000000,60')), 'Jan 1, 2026 at 00:59');
  assert.equal(startText('shake.txt.gz', linesWith('> CLOCK,1577836800000000,0')), 'Jan 1, 2020 at 00:00');

  const toneFirst = linesWith();
  toneFirst.splice(3, 0, '> TONE,1');
  assert.equal(startText('shake.txt.gz', toneFirst), null);
  for (const clock of [
    '> CLOCK,abc,0',
    '> CLOCK,1577836799999999,0',
    '> CLOCK,4102444800000000,0',
    '> CLOCK,1793209555689292,841',
    '> CLOCK,1793209555689292,-721',
  ]) {
    assert.equal(startText('shake.txt.gz', linesWith(clock)), null, clock);
  }
  const clockFirst = linesWith().filter((line) => line !== CLOCK);
  clockFirst.splice(1, 0, CLOCK);
  assert.equal(startText('shake.txt.gz', clockFirst), null);
  assert.equal(startText('shake.txt.gz', linesWith().filter((line) => !line.startsWith('B,'))), null);
  assert.equal(startText('tremor-2026-10-28-142813.txt.gz', linesWith()), 'Oct 28, 2026 at 14:28');

  for (const name of ['record_log', 'command_log', 'drop_log', 'face_log']) {
    assert.equal(loadRecording(log(name)).startText, null, name);
  }
  assert.equal(loadRecording(SYNTHETIC).startText, null);
  const copy = path.join(tempFolder(), 'tremor-2026-10-28-142813.txt.gz');
  fs.copyFileSync(SYNTHETIC, copy);
  assert.equal(loadRecording(copy).startText, 'Oct 28, 2026 at 14:28');
});
