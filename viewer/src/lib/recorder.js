'use strict';

// Runs `tools/watch_cli.py record` as a child process for the Record button.
// watch_cli.py stays the only program that talks to the watch, so the viewer
// never opens the port itself. This module uses no Electron, so its tests run
// with plain Node.

const { spawn } = require('node:child_process');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { RecordError } = require('./errors');

const REPO = path.join(__dirname, '..', '..', '..');
// The ESP-IDF Python, which holds pyserial, as specs/tech-stack.md says.
const PYTHON_UNDER_HOME = path.join('.espressif', 'tools', 'python', 'v6.1', 'venv', 'bin', 'python');
const DEFAULT_PYTHON = path.join(os.homedir(), PYTHON_UNDER_HOME);
// The wait after SIGINT before the viewer ends watch_cli.py with SIGKILL.
const KILL_AFTER_MS = 10000;
// The number of watch_cli.py's standard error lines that a recording keeps.
const KEPT_LINES = 50;
// record() writes lines that start like this on every stop, so they never
// say why a recording failed.
const STOP_LINE_STARTS = ['Saved ', 'The recording was stopped'];
const NO_PYSERIAL = "No module named 'serial'";
const SUFFIX = '.txt.gz';

/**
 * Give the Python, watch_cli.py, and the recordings folder from the
 * environment. Relative paths in TREMOR_PYTHON and TREMOR_RECORDINGS resolve
 * against cwd, the folder the command ran from.
 *
 * @param {{env?: object, home?: string, cwd?: string, repo?: string}} where
 * @returns {{python: string, script: string, folder: string}}
 */
function recorderSettings({ env = process.env, home = os.homedir(), cwd = process.cwd(), repo = REPO } = {}) {
  return {
    python: env.TREMOR_PYTHON ? path.resolve(cwd, env.TREMOR_PYTHON) : path.join(home, PYTHON_UNDER_HOME),
    script: path.join(repo, 'tools', 'watch_cli.py'),
    folder: env.TREMOR_RECORDINGS ? path.resolve(cwd, env.TREMOR_RECORDINGS) : path.join(repo, 'recordings'),
  };
}

/**
 * Give the file name for a recording that starts at date, in local time.
 *
 * @param {Date} date
 * @returns {string} Such as tremor-2026-10-28-143005.txt.gz.
 */
function recordingName(date) {
  const two = (n) => String(n).padStart(2, '0');
  const day = `${date.getFullYear()}-${two(date.getMonth() + 1)}-${two(date.getDate())}`;
  const time = `${two(date.getHours())}${two(date.getMinutes())}${two(date.getSeconds())}`;
  return `tremor-${day}-${time}${SUFFIX}`;
}

/**
 * Make the folder when it is missing and give the first free path of the
 * series NAME.txt.gz, NAME-2.txt.gz, NAME-3.txt.gz, and so on.
 *
 * @param {string} folder
 * @param {Date} date
 * @returns {string}
 */
function freeRecordingPath(folder, date) {
  fs.mkdirSync(folder, { recursive: true });
  const stem = recordingName(date).slice(0, -SUFFIX.length);
  for (let n = 1; ; n++) {
    const file = path.join(folder, n === 1 ? `${stem}${SUFFIX}` : `${stem}-${n}${SUFFIX}`);
    // lstat counts a broken link as taken, as watch_cli.py's open does.
    if (fs.lstatSync(file, { throwIfNoEntry: false }) === undefined) {
      return file;
    }
  }
}

/**
 * Give the line of watch_cli.py's standard error that says why it stopped:
 * the last line that is not one of the lines every stop writes, or the last
 * line when there is no other.
 *
 * @param {string[]} lines
 * @returns {string | null}
 */
function errorLine(lines) {
  const telling = lines.filter((line) => !STOP_LINE_STARTS.some((start) => line.startsWith(start)));
  return telling.at(-1) ?? lines.at(-1) ?? null;
}

function checkPython(python) {
  const fix = 'Set TREMOR_PYTHON to the path of a Python that holds pyserial.';
  if (!fs.existsSync(python)) {
    throw new RecordError(`There is no Python at ${python}. ${fix}`);
  }
  try {
    fs.accessSync(python, fs.constants.X_OK);
  } catch {
    throw new RecordError(`The Python at ${python} cannot run. ${fix}`);
  }
  if (!fs.statSync(python).isFile()) {
    throw new RecordError(`The Python at ${python} is not a file. ${fix}`);
  }
}

function checkScript(script) {
  if (!fs.statSync(script, { throwIfNoEntry: false })?.isFile()) {
    throw new RecordError(`There is no watch_cli.py at ${script}.`);
  }
}

/** Describe how the child ended, as requirement 16 of feature 14 says. */
function outcomeOf(run, code, signal, killAfterMs) {
  const fileExists = fs.existsSync(run.file);
  const ended = { file: run.file, code, signal, killed: run.killed, fileExists };
  if (signal !== null) {
    const how = run.killed
      ? `watch_cli.py did not stop within ${killAfterMs / 1000} seconds of SIGINT, so the viewer ended it with SIGKILL.`
      : `watch_cli.py was ended by ${signal}.`;
    const cut = fileExists ? ` The file ${run.file} may be cut short.` : '';
    return { ...ended, open: false, ok: false, text: how + cut };
  }
  if (code === 0) {
    const saved = run.lines.findLast((line) => line.startsWith('Saved ')) ?? `watch_cli.py saved ${run.file}.`;
    return { ...ended, open: true, ok: true, text: saved };
  }
  const line = errorLine(run.lines);
  let text = line === null
    ? `watch_cli.py stopped with code ${code} and wrote no message.`
    : `watch_cli.py stopped with code ${code}: ${line}`;
  if (line !== null && line.includes(NO_PYSERIAL)) {
    text += ' This Python has no pyserial. Set TREMOR_PYTHON to the ESP-IDF Python, which holds it.';
  }
  return { ...ended, open: fileExists, ok: false, text };
}

/**
 * Runs one recording at a time. It emits `status` with
 * {state, startedAt, file, text, ok} for each line watch_cli.py writes and
 * each change of state, and `done` with the outcome when a recording ends.
 * The state is 'idle', 'recording', or 'stopping'.
 */
class Recorder extends EventEmitter {
  #python;
  #script;
  #folder;
  #env;
  #now;
  #killAfterMs;
  #run = null;

  /**
   * @param {{python: string, script: string, folder: string, env?: object, now?: () => Date, killAfterMs?: number}} settings
   */
  constructor({ python, script, folder, env = process.env, now = () => new Date(), killAfterMs = KILL_AFTER_MS }) {
    super();
    this.#python = python;
    this.#script = script;
    this.#folder = folder;
    this.#env = env;
    this.#now = now;
    this.#killAfterMs = killAfterMs;
    this.state = 'idle';
  }

  /**
   * Start watch_cli.py record on a new file. It throws a RecordError, and
   * starts nothing, when a recording runs or the Python, watch_cli.py, or the
   * folder is not there.
   *
   * @returns {{file: string, startedAt: number}} The file and the start in milliseconds since 1970.
   */
  start() {
    if (this.state !== 'idle') {
      throw new RecordError('A recording is running already.');
    }
    checkPython(this.#python);
    checkScript(this.#script);
    const startedAt = this.#now();
    let file;
    try {
      file = freeRecordingPath(this.#folder, startedAt);
    } catch (err) {
      throw new RecordError(`Could not make the folder ${this.#folder} for recordings (${err.code ?? err.message}).`);
    }
    let child;
    try {
      // An argument array and no shell, so no path is ever read as a command.
      child = spawn(this.#python, [this.#script, 'record', '--out', file], {
        cwd: REPO,
        env: { ...this.#env, PYTHONUNBUFFERED: '1' },
        stdio: ['ignore', 'pipe', 'pipe'],
      });
    } catch (err) {
      throw new RecordError(`Could not start ${this.#python} (${err.code ?? err.message}).`);
    }

    const run = { child, file, startedAt: startedAt.getTime(), lines: [], killTimer: null, killed: false, ended: false };
    run.done = new Promise((resolve) => {
      run.resolve = resolve;
    });
    this.#run = run;
    this.state = 'recording';

    child.stdout.resume();
    this.#readLines(run);
    // An error with no pid means the child never started, as with EACCES.
    // Other errors, such as a failed kill, leave the child to close.
    child.on('error', (err) => {
      if (child.pid === undefined) {
        this.#end(run, {
          file,
          code: null,
          signal: null,
          killed: false,
          fileExists: fs.existsSync(file),
          open: false,
          ok: false,
          text: `Could not start ${this.#python} (${err.code ?? err.message}).`,
        });
      }
    });
    // close comes after the standard error has ended, so every line is read.
    child.on('close', (code, signal) => this.#end(run, outcomeOf(run, code, signal, this.#killAfterMs)));
    this.#sendStatus(run);
    return { file, startedAt: run.startedAt };
  }

  /**
   * Stop the recording as Ctrl-C does. A second call gives the same promise
   * and sends no second signal.
   *
   * @returns {Promise<object | null>} The outcome, or null when no recording runs.
   */
  stop() {
    const run = this.#run;
    if (run === null) {
      return Promise.resolve(null);
    }
    if (this.state === 'recording') {
      this.state = 'stopping';
      run.child.kill('SIGINT');
      run.killTimer = setTimeout(() => {
        run.killed = true;
        run.child.kill('SIGKILL');
      }, this.#killAfterMs);
      this.#sendStatus(run);
    }
    return run.done;
  }

  #readLines(run) {
    const take = (raw) => {
      const line = raw.trimEnd();
      if (line === '') {
        return;
      }
      run.lines.push(line);
      if (run.lines.length > KEPT_LINES) {
        run.lines.shift();
      }
      this.#sendStatus(run);
    };
    let rest = '';
    const stderr = run.child.stderr;
    stderr.setEncoding('utf8');
    stderr.on('data', (chunk) => {
      const parts = (rest + chunk).split('\n');
      rest = parts.pop();
      parts.forEach(take);
    });
    stderr.on('end', () => take(rest));
  }

  #sendStatus(run, text = run.lines.at(-1) ?? null, ok = null) {
    this.emit('status', { state: this.state, startedAt: run.startedAt, file: run.file, text, ok });
  }

  /** End the recording once, whichever of close and a spawn error comes first. */
  #end(run, outcome) {
    if (run.ended) {
      return;
    }
    run.ended = true;
    clearTimeout(run.killTimer);
    this.#run = null;
    this.state = 'idle';
    try {
      this.#sendStatus(run, outcome.text, outcome.ok);
      this.emit('done', outcome);
    } finally {
      run.resolve(outcome);
    }
  }
}

module.exports = {
  DEFAULT_PYTHON,
  KILL_AFTER_MS,
  Recorder,
  errorLine,
  freeRecordingPath,
  recorderSettings,
  recordingName,
};
