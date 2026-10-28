'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const test = require('node:test');
const { readRecordingLines } = require('../src/lib/read_text');
const { RecordingError } = require('../src/lib/errors');
const { log } = require('./helpers/paths');
const { tempFolder } = require('./helpers/temp');

const dir = tempFolder();
const RECORD_LOG = log('record_log');

test('case 2: a whole gzip file and one cut short', () => {
  const raw = zlib.gunzipSync(fs.readFileSync(RECORD_LOG)).toString('utf8').split('\n');
  raw.pop();
  const whole = readRecordingLines(RECORD_LOG);
  assert.equal(whole.cutShort, false);
  assert.equal(whole.lines.length, raw.length);
  whole.lines.forEach((line, i) => assert.equal(line, raw[i].slice(raw[i].indexOf('\t') + 1)));

  const bytes = fs.readFileSync(RECORD_LOG);
  const half = path.join(dir, 'half.txt.gz');
  fs.writeFileSync(half, bytes.subarray(0, Math.floor(bytes.length / 2)));
  const cut = readRecordingLines(half);
  assert.equal(cut.cutShort, true);
  assert.ok(cut.lines.length >= 1);
  assert.deepEqual(cut.lines, whole.lines.slice(0, cut.lines.length));
});

test('case 3: plain text, a file that is not gzip, a missing file, and the size limit', () => {
  const plain = path.join(dir, 'x.txt');
  fs.writeFileSync(plain, '0.001\tB,1,11,12,H\r\nR,0,1,2,3,4,5,6\n');
  assert.deepEqual(readRecordingLines(plain).lines, ['B,1,11,12,H', 'R,0,1,2,3,4,5,6']);

  const bad = path.join(dir, 'bad.gz');
  fs.writeFileSync(bad, 'hello');
  assert.throws(() => readRecordingLines(bad), (err) => err instanceof RecordingError && err.message.includes('not a gzip file'));

  const missing = path.join(dir, 'missing.txt.gz');
  assert.throws(() => readRecordingLines(missing), (err) => err instanceof RecordingError && err.message.includes(missing));

  assert.throws(
    () => readRecordingLines(RECORD_LOG, { maxBytes: 1000 }),
    (err) => err instanceof RecordingError && err.message.includes('1000 bytes'),
  );
});
