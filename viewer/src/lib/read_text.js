'use strict';

const fs = require('node:fs');
const zlib = require('node:zlib');
const { RecordingError } = require('./errors');

// Ten times the text of a two hour session.
const MAX_BYTES = 400 * 1024 * 1024;
const MB = 1024 * 1024;

// The laptop time that tools/watch_cli.py writes before the tab. Any decimal
// number counts, as float() in read_recording() of tools/compare_session.py
// takes it.
const LAPTOP_TIME = /^[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?$/;

const READ_PROBLEMS = {
  ENOENT: 'it does not exist',
  EACCES: 'permission was denied',
  EISDIR: 'it is a folder',
};

function limitText(maxBytes) {
  return maxBytes % MB === 0 ? `${maxBytes / MB} MB` : `${maxBytes} bytes`;
}

function tooLong(filePath, maxBytes) {
  return new RecordingError(`${filePath} holds more than ${limitText(maxBytes)} of text, which is the most the viewer reads.`);
}

function readProblem(filePath, err) {
  const why = READ_PROBLEMS[err.code] || err.message;
  return new RecordingError(`Could not read ${filePath}, because ${why}.`);
}

function isTooLarge(err) {
  return err.code === 'ERR_BUFFER_TOO_LARGE';
}

function isCutShort(err) {
  return err.code === 'Z_BUF_ERROR' || /unexpected end of file/.test(err.message);
}

/** Unzip the bytes. A stream that stops early gives the text up to the cut. */
function gunzip(bytes, filePath, maxBytes) {
  try {
    return { buffer: zlib.gunzipSync(bytes, { maxOutputLength: maxBytes }), cutShort: false };
  } catch (err) {
    if (isTooLarge(err)) {
      throw tooLong(filePath, maxBytes);
    }
    if (!isCutShort(err)) {
      throw new RecordingError(`${filePath} is not a gzip file.`);
    }
  }
  try {
    const options = { maxOutputLength: maxBytes, finishFlush: zlib.constants.Z_SYNC_FLUSH };
    return { buffer: zlib.gunzipSync(bytes, options), cutShort: true };
  } catch (err) {
    throw isTooLarge(err) ? tooLong(filePath, maxBytes) : new RecordingError(`${filePath} is not a gzip file.`);
  }
}

function readBytes(filePath, maxBytes, isGzip) {
  try {
    if (!isGzip && fs.statSync(filePath).size > maxBytes) {
      throw tooLong(filePath, maxBytes);
    }
    return fs.readFileSync(filePath);
  } catch (err) {
    throw err instanceof RecordingError ? err : readProblem(filePath, err);
  }
}

function dropLaptopTime(line) {
  const tab = line.indexOf('\t');
  if (tab < 0 || !LAPTOP_TIME.test(line.slice(0, tab))) {
    return line;
  }
  return line.slice(tab + 1);
}

/**
 * Read the lines of a saved recording, gzip when the name ends in .gz and
 * plain text otherwise, with each line's laptop time and tab dropped.
 *
 * A gzip file that was cut short is read up to the cut, and its last line is
 * dropped when it has no newline, because it may be part of a line.
 *
 * @param {string} filePath The recording.
 * @param {{maxBytes?: number}} [options] The most text to read.
 * @returns {{lines: string[], cutShort: boolean}}
 */
function readRecordingLines(filePath, { maxBytes = MAX_BYTES } = {}) {
  const isGzip = filePath.endsWith('.gz');
  const bytes = readBytes(filePath, maxBytes, isGzip);
  const { buffer, cutShort } = isGzip ? gunzip(bytes, filePath, maxBytes) : { buffer: bytes, cutShort: false };
  const lines = buffer.toString('utf8').split('\n');
  // The piece after the last newline is empty, or it is a line cut by the end.
  const last = lines.pop();
  if (last !== '' && !cutShort) {
    lines.push(last);
  }
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].endsWith('\r') ? lines[i].slice(0, -1) : lines[i];
    lines[i] = dropLaptopTime(line);
  }
  return { lines, cutShort };
}

module.exports = { readRecordingLines, MAX_BYTES };
