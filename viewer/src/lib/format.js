'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { RecordingError } = require('./errors');

const FORMAT_DOC = path.join(__dirname, '..', '..', '..', 'core', 'recording_format.md');
const RECORD_LETTERS = ['A', 'B', 'D', 'F', 'R', 'S', 'T', 'W'];

// The row pattern of record_patterns() in tools/compare_session.py.
const TABLE_ROW = /^\| ([A-Z]) \|.*\| `(\^.*\$)` \|$/;

/**
 * Read the pattern of each record line from the table in core/recording_format.md.
 *
 * @param {string} [docPath] The format document.
 * @returns {Record<string, RegExp>} One pattern for each of A, B, D, F, R, S, T, and W.
 */
function readRecordPatterns(docPath = FORMAT_DOC) {
  let text;
  try {
    text = fs.readFileSync(docPath, 'utf8');
  } catch (err) {
    throw new RecordingError(`Could not read the record patterns from ${docPath} (${err.code || err.message}).`);
  }
  const patterns = {};
  for (const row of text.split(/\r?\n/)) {
    const found = TABLE_ROW.exec(row);
    if (found && RECORD_LETTERS.includes(found[1])) {
      patterns[found[1]] = new RegExp(found[2]);
    }
  }
  const missing = RECORD_LETTERS.filter((letter) => !(letter in patterns));
  if (missing.length > 0) {
    throw new RecordingError(`${docPath} gives no record pattern for ${missing.join(', ')}.`);
  }
  return patterns;
}

module.exports = { readRecordPatterns, FORMAT_DOC, RECORD_LETTERS };
