'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const test = require('node:test');
const { readRecordPatterns } = require('../src/lib/format');
const { RecordingError } = require('../src/lib/errors');
const { FORMAT_DOC, log } = require('./helpers/paths');
const { tempFolder } = require('./helpers/temp');

test('case 1: the record patterns come from core/recording_format.md', () => {
  const patterns = readRecordPatterns();
  assert.deepEqual(Object.keys(patterns).sort(), ['A', 'B', 'D', 'F', 'R', 'S', 'T', 'W']);

  const raw = zlib.gunzipSync(fs.readFileSync(log('record_log'))).toString('utf8').split('\n');
  const firstB = raw.map((line) => line.slice(line.indexOf('\t') + 1)).find((text) => text.startsWith('B,'));
  assert.match(firstB, patterns.B);
  assert.match('W,3,,4,,,', patterns.W);
  assert.match('W,0,7,0,0.5,10,5', patterns.W);

  const doc = path.join(tempFolder(), 'recording_format.md');
  const withoutW = fs
    .readFileSync(FORMAT_DOC, 'utf8')
    .split('\n')
    .filter((row) => !row.startsWith('| W |'))
    .join('\n');
  fs.writeFileSync(doc, withoutW);
  assert.throws(() => readRecordPatterns(doc), (err) => err instanceof RecordingError && err.message.includes('W'));
});
