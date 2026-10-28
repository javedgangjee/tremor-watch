'use strict';

// Check 1 cases 1 to 12 of specs/features/14-record-button/validation.md. The
// recorder runs test/helpers/fake_watch_cli.js with Node as the Python.

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { performance } = require('node:perf_hooks');
const test = require('node:test');
const zlib = require('node:zlib');
const { RecordError } = require('../src/lib/errors');
const { Recorder, errorLine, freeRecordingPath, recorderSettings, recordingName } = require('../src/lib/recorder');
const { FAKE_LINES } = require('./helpers/fake_watch_cli');
const { tempFolder } = require('./helpers/temp');

const FAKE = path.join(__dirname, 'helpers', 'fake_watch_cli.js');
const NOW = new Date(2026, 9, 28, 14, 30, 5);
const NAME = 'tremor-2026-10-28-143005.txt.gz';
const WAIT_LIMIT_MS = 10000;

/** A recorder that runs the fake with these orders. */
function recorderIn(folder, orders = {}, settings = {}) {
  return new Recorder({
    python: process.execPath,
    script: FAKE,
    folder,
    env: { ...process.env, FAKE_WATCH_CLI: JSON.stringify(orders) },
    now: () => NOW,
    ...settings,
  });
}

/** Resolve with the promise's value, or fail after WAIT_LIMIT_MS so a hung child fails the test. */
function within(promise, what) {
  let timer;
  const limit = new Promise((_resolve, reject) => {
    timer = setTimeout(() => reject(new Error(`${what} did not come within ${WAIT_LIMIT_MS} ms`)), WAIT_LIMIT_MS);
  });
  return Promise.race([promise, limit]).finally(() => clearTimeout(timer));
}

/** The first status event that passes the test. */
function statusWhere(recorder, wanted, what) {
  return within(
    new Promise((resolve) => {
      const listener = (status) => {
        if (wanted(status)) {
          recorder.off('status', listener);
          resolve(status);
        }
      };
      recorder.on('status', listener);
    }),
    what,
  );
}

const savingLine = (file) => `Saving the recording to ${file}. Press Ctrl-C to stop.`;

/** Wait for the fake's first line, which it writes once its SIGINT handler is in place. */
function saving(recorder, file) {
  return statusWhere(recorder, (s) => s.text === savingLine(file), 'the first line');
}

const gunzipText = (file) => zlib.gunzipSync(fs.readFileSync(file)).toString('utf8');
const linesOf = (file) => (fs.existsSync(file) ? fs.readFileSync(file, 'utf8').split('\n').filter(Boolean) : []);

/** The outcome of case 3, a clean stop. */
function assertSaved(outcome, file) {
  assert.equal(outcome.file, file);
  assert.equal(outcome.code, 0);
  assert.equal(outcome.signal, null);
  assert.equal(outcome.open, true);
  assert.equal(outcome.ok, true);
  assert.equal(outcome.text, `Saved 3 lines to ${file}.`);
  assert.equal(gunzipText(file), `${FAKE_LINES.join('\n')}\n`);
}

test('case 1 of feature 14: recording names and free paths', () => {
  assert.equal(recordingName(NOW), NAME);
  const folder = path.join(tempFolder(), 'new', 'recordings');
  const first = freeRecordingPath(folder, NOW);
  assert.ok(fs.statSync(folder).isDirectory());
  assert.equal(first, path.join(folder, NAME));
  assert.ok(!fs.existsSync(first));
  fs.writeFileSync(first, 'x');
  const second = freeRecordingPath(folder, NOW);
  assert.equal(second, path.join(folder, 'tremor-2026-10-28-143005-2.txt.gz'));
  assert.ok(!fs.existsSync(second));
  fs.writeFileSync(second, 'x');
  const third = freeRecordingPath(folder, NOW);
  assert.equal(third, path.join(folder, 'tremor-2026-10-28-143005-3.txt.gz'));
  assert.ok(!fs.existsSync(third));
});

test('case 2 of feature 14: the settings from the environment', () => {
  assert.deepEqual(recorderSettings({ env: {}, home: '/h', cwd: '/c', repo: '/r' }), {
    python: '/h/.espressif/tools/python/v6.1/venv/bin/python',
    script: '/r/tools/watch_cli.py',
    folder: '/r/recordings',
  });
  const env = { TREMOR_PYTHON: '/p/python', TREMOR_RECORDINGS: 'rec' };
  assert.deepEqual(recorderSettings({ env, home: '/h', cwd: '/c', repo: '/r' }), {
    python: '/p/python',
    script: '/r/tools/watch_cli.py',
    folder: '/c/rec',
  });
});

test('case 3 of feature 14: a recording runs, stops at SIGINT, and saves its file', async () => {
  const dir = tempFolder();
  const folder = path.join(dir, 'my $HOME recordings');
  const argsOut = path.join(dir, 'args.json');
  const sigintOut = path.join(dir, 'sigint.txt');
  const recorder = recorderIn(folder, { argsOut, sigintOut });
  const states = [];
  recorder.on('status', (s) => {
    if (states.at(-1) !== s.state) {
      states.push(s.state);
    }
  });
  const file = path.join(folder, NAME);
  const first = saving(recorder, file);
  assert.equal(recorder.start().file, file);
  await first;
  const outcome = await within(recorder.stop(), 'the outcome');

  const seen = JSON.parse(fs.readFileSync(argsOut, 'utf8'));
  assert.deepEqual(seen.args, [FAKE, 'record', '--out', file]);
  assert.equal(seen.PYTHONUNBUFFERED, '1');
  assert.deepEqual(states, ['recording', 'stopping', 'idle']);
  assert.equal(linesOf(sigintOut).length, 1);
  assertSaved(outcome, file);
});

test('case 4 of feature 14: each line of the standard error shows while recording', async () => {
  const recorder = recorderIn(tempFolder(), { startLines: ['The watch set its clock.'] });
  const clockSet = statusWhere(recorder, (s) => s.text === 'The watch set its clock.', 'the clock line');
  recorder.start();
  const status = await clockSet;
  assert.equal(status.state, 'recording');
  await within(recorder.stop(), 'the outcome');
});

test('case 5 of feature 14: a failed clock command still opens the whole file', async () => {
  const line = 'The clock command got result 4. The watch applied the setting but could not store it, so a restart loses it.';
  const recorder = recorderIn(tempFolder(), { stopLines: [line], exitCode: 1 });
  const { file } = recorder.start();
  await saving(recorder, file);
  const outcome = await within(recorder.stop(), 'the outcome');
  assert.equal(outcome.code, 1);
  assert.equal(outcome.open, true);
  assert.equal(outcome.ok, false);
  assert.equal(outcome.fileExists, true);
  assert.equal(outcome.text, `watch_cli.py stopped with code 1: ${line}`);
  assert.equal(gunzipText(file), `${FAKE_LINES.join('\n')}\n`);
});

test('case 6 of feature 14: watch_cli.py stops on its own when the port cannot be opened', async () => {
  const serialLine =
    "serial.serialutil.SerialException: [Errno 2] could not open port /x: [Errno 2] No such file or directory: '/x'";
  const recorder = recorderIn(tempFolder(), { startLines: ['Traceback (most recent call last):', serialLine], dieWith: 1 });
  const done = within(new Promise((resolve) => recorder.once('done', resolve)), 'done');
  recorder.start();
  const outcome = await done;
  assert.equal(outcome.code, 1);
  assert.equal(outcome.fileExists, false);
  assert.equal(outcome.open, false);
  assert.equal(outcome.ok, false);
  assert.ok(outcome.text.endsWith(serialLine), outcome.text);
  assert.equal(recorder.state, 'idle');

  const noSerial = recorderIn(tempFolder(), { startLines: ["ModuleNotFoundError: No module named 'serial'"], dieWith: 1 });
  const noSerialDone = within(new Promise((resolve) => noSerial.once('done', resolve)), 'done');
  noSerial.start();
  const { text } = await noSerialDone;
  assert.ok(text.includes('pyserial') && text.includes('TREMOR_PYTHON'), text);
});

test('case 7 of feature 14: a second stop and a second start', async () => {
  const dir = tempFolder();
  const sigintOut = path.join(dir, 'sigint.txt');
  const recorder = recorderIn(path.join(dir, 'rec'), { sigintOut });
  const { file } = recorder.start();
  await saving(recorder, file);
  assert.throws(() => recorder.start(), RecordError);
  assert.equal(recorder.state, 'recording');
  const stopped = recorder.stop();
  assert.equal(recorder.stop(), stopped);
  const outcome = await within(stopped, 'the outcome');
  assert.equal(linesOf(sigintOut).length, 1);
  assertSaved(outcome, file);
  assert.equal(await recorder.stop(), null);
});

test('case 8 of feature 14: stop() waits for watch_cli.py to close its file', async () => {
  const recorder = recorderIn(tempFolder(), { closeDelayMs: 500 });
  const { file } = recorder.start();
  await saving(recorder, file);
  const asked = performance.now();
  await within(recorder.stop(), 'the outcome');
  const waited = performance.now() - asked;
  assert.ok(waited >= 450, `stop() resolved after ${waited} ms`);
  assert.equal(gunzipText(file), `${FAKE_LINES.join('\n')}\n`);
});

test('case 9 of feature 14: a child that ignores SIGINT gets SIGKILL', async () => {
  const recorder = recorderIn(tempFolder(), { ignoreInt: true }, { killAfterMs: 300 });
  const { file } = recorder.start();
  await saving(recorder, file);
  const outcome = await within(recorder.stop(), 'the outcome');
  assert.equal(outcome.signal, 'SIGKILL');
  assert.equal(outcome.killed, true);
  assert.equal(outcome.open, false);
  assert.ok(outcome.text.includes('watch_cli.py did not stop'), outcome.text);
  assert.ok(outcome.text.includes('may be cut short'), outcome.text);
});

test('case 10 of feature 14: a missing Python or watch_cli.py starts nothing', () => {
  const folder = tempFolder();
  const missing = path.join(folder, 'no-such-python');
  const noPython = recorderIn(folder, {}, { python: missing });
  assert.throws(
    () => noPython.start(),
    (err) => err instanceof RecordError && err.message.includes(missing) && err.message.includes('TREMOR_PYTHON'),
  );
  assert.equal(noPython.state, 'idle');

  const plain = path.join(tempFolder(), 'python');
  fs.writeFileSync(plain, '#!/bin/sh\n', { mode: 0o644 });
  fs.chmodSync(plain, 0o644);
  const notRunnable = recorderIn(folder, {}, { python: plain });
  assert.throws(() => notRunnable.start(), RecordError);
  assert.equal(notRunnable.state, 'idle');

  const script = path.join(folder, 'no-such-watch_cli.py');
  const noScript = recorderIn(folder, {}, { script });
  assert.throws(() => noScript.start(), (err) => err instanceof RecordError && err.message.includes(script));
  assert.equal(noScript.state, 'idle');

  assert.deepEqual(fs.readdirSync(folder), []);
});

test('case 11 of feature 14: a taken name gets -2, and the taken file is kept', async () => {
  const folder = tempFolder();
  const taken = path.join(folder, NAME);
  fs.writeFileSync(taken, 'keep');
  const recorder = recorderIn(folder);
  const { file } = recorder.start();
  assert.equal(file, path.join(folder, 'tremor-2026-10-28-143005-2.txt.gz'));
  await saving(recorder, file);
  assertSaved(await within(recorder.stop(), 'the outcome'), file);
  assert.equal(fs.readFileSync(taken, 'utf8'), 'keep');
});

test('case 12 of feature 14: the line that says why watch_cli.py stopped', () => {
  assert.equal(
    errorLine(['a', 'The clock command got no answer.', 'The recording was stopped by SIGTERM.', 'Saved 10 lines to F.']),
    'The clock command got no answer.',
  );
  assert.equal(errorLine(['a', 'b']), 'b');
  assert.equal(errorLine(['Saved 1 lines to F.']), 'Saved 1 lines to F.');
  assert.equal(errorLine([]), null);
});
