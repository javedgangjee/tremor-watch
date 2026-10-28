'use strict';

// Runs the real app in capture mode on the cases of check 2 in
// specs/features/12-recording-viewer/validation.md and
// specs/features/14-record-button/validation.md, prints one line per case,
// and exits with code 1 when a case fails. It needs the installed packages and
// a logged-in screen. The record cases run test/helpers/fake_watch_cli.js in
// place of watch_cli.py, so they need no watch.
//
//   npm --prefix viewer run smoke -- [--out DIR]

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const electron = require('electron');
const { BOOT_B, RATE_UHZ } = require('../test/helpers/synthetic');

const VIEWER = path.join(__dirname, '..');
const REPO = path.join(VIEWER, '..');
const SYNTHETIC = path.join(VIEWER, 'test', 'fixtures', 'synthetic.txt.gz');
const MAKE_SYNTHETIC = path.join(__dirname, 'make_synthetic.js');
const FAKE_WATCH_CLI = path.join(VIEWER, 'test', 'helpers', 'fake_watch_cli.js');
const RECORDING_NAME = /^tremor-\d{4}-\d{2}-\d{2}-\d{6}\.txt\.gz$/;
const log = (name) => path.join(REPO, 'tests', 'firmware', `${name}.txt.gz`);
const CASE_LIMIT_MS = 90000;
const DRAW_LIMIT_MS = 10000;

function outFolder(argv) {
  if (argv.length === 2 && argv[0] === '--out') {
    fs.mkdirSync(argv[1], { recursive: true });
    return path.resolve(argv[1]);
  }
  if (argv.length === 0) {
    return fs.mkdtempSync(path.join(os.tmpdir(), 'tremor-viewer-smoke-'));
  }
  console.error('Usage: npm --prefix viewer run smoke -- [--out DIR]');
  process.exit(2);
}

/** Quote a path for sh. */
const shellQuote = (text) => `'${text.replaceAll("'", "'\\''")}'`;

/** Write OUT/fake-python, which runs the fake watch_cli.py with this Node, and give its path. */
function writeFakePython(out) {
  const fake = path.join(out, 'fake-python');
  fs.writeFileSync(fake, `#!/bin/sh\nexec ${shellQuote(process.execPath)} ${shellQuote(FAKE_WATCH_CLI)} "$@"\n`);
  fs.chmodSync(fake, 0o755);
  return fake;
}

/** Remove a folder and make it again empty. */
function newFolder(folder) {
  fs.rmSync(folder, { recursive: true, force: true });
  fs.mkdirSync(folder, { recursive: true });
  return folder;
}

/**
 * Run the app on one case and give its exit code, its JSON, and whether its
 * PNG exists. env holds variables to add to the app's environment.
 */
function runApp(out, name, appArgs, env = {}) {
  const png = path.join(out, `${name}.png`);
  const json = path.join(out, `${name}.json`);
  fs.rmSync(png, { force: true });
  fs.rmSync(json, { force: true });
  const run = spawnSync(electron, [VIEWER, ...appArgs, '--capture', png], {
    encoding: 'utf8',
    timeout: CASE_LIMIT_MS,
    env: { ...process.env, ...env },
  });
  return {
    code: run.status,
    result: fs.existsSync(json) ? JSON.parse(fs.readFileSync(json, 'utf8')) : null,
    hasPng: fs.existsSync(png),
  };
}

/** Collects the checks of one case that fail. */
function checker() {
  const failures = [];
  return {
    failures,
    equal(what, actual, expected) {
      if (JSON.stringify(actual) !== JSON.stringify(expected)) {
        failures.push(`${what} is ${JSON.stringify(actual)}, not ${JSON.stringify(expected)}`);
      }
    },
    ok(what, value) {
      if (!value) {
        failures.push(what);
      }
    },
  };
}

const codes = (report, wanted) => wanted.map((code) => report.windowsByCode[code]);

// Each case runs the app with run(name, args), which captures to
// OUT/<name>.png and OUT/<name>.json.
const CASES = [
  {
    name: 'case 27 synthetic',
    test(c, run) {
      const { code, result } = run('synthetic', [SYNTHETIC]);
      c.equal('exit code', code, 0);
      const { report, webPreferences: prefs } = result;
      c.equal('boot', report.bootId, 305419896);
      c.equal('readings', report.readings, 18260);
      c.equal('windows of codes 0 to 3', codes(report, [0, 1, 2, 3]), [39, 92, 18, 2]);
      c.equal('tremor cells', report.tremorCells.length, 39);
      c.equal('tremor cell pixels', [result.tremorCellPixels.checked, result.tremorCellPixels.matched], [39, 39]);
      c.equal(
        'web preferences',
        [prefs.contextIsolation, prefs.nodeIntegration, prefs.sandbox, prefs.webSecurity],
        [true, false, true, true],
      );
      c.equal('require and process in the page', [result.pageHasRequire, result.pageHasProcess], [false, false]);
      return result;
    },
  },
  {
    name: 'case 28 synthetic boot B',
    test(c, run) {
      const { code, result } = run('synthetic_boot_b', [SYNTHETIC, '--boot', String(BOOT_B)]);
      c.equal('exit code', code, 0);
      c.equal('readings', result.report.readings, 913);
      c.equal('estimated stretches', result.report.stretches.map((s) => s.estimated), [true]);
      c.equal('tremor cells', result.report.tremorCells.length, 0);
      return result;
    },
  },
  {
    name: 'case 29 record_log',
    test(c, run) {
      const { code, result } = run('record_log', [log('record_log')]);
      c.equal('exit code', code, 0);
      c.equal('readings', result.report.readings, 206041);
      c.equal('windows of codes 1 and 3', codes(result.report, [1, 3]), [1797, 1]);
      c.equal('tremor cells', result.report.tremorCells.length, 0);
      return result;
    },
  },
  {
    name: 'case 30 command_log',
    test(c, run) {
      const { code, result } = run('command_log', [log('command_log'), '--boot', '505078862']);
      c.equal('exit code', code, 0);
      c.equal('readings', result.report.readings, 144078);
      c.equal('stretches', result.report.stretches.length, 2);
      return result;
    },
  },
  {
    name: 'case 31 bad and missing files',
    test(c, run, out) {
      const bad = path.join(out, 'bad.gz');
      fs.writeFileSync(bad, 'hello');
      const badRun = run('bad_file', [bad]);
      c.equal('exit code for bad.gz', badRun.code, 1);
      c.ok('the message says "not a gzip file"', badRun.result && /not a gzip file/.test(badRun.result.message));
      c.ok('the PNG of bad.gz exists', badRun.hasPng);
      const missing = run('missing_file', [path.join(out, 'no-such-recording.txt.gz')]);
      c.equal('exit code for a missing file', missing.code, 1);
      return badRun.result;
    },
  },
  {
    name: 'case 32 bad option',
    test(c, run) {
      const { code, result } = run('bad_option', ['--frob']);
      c.equal('exit code', code, 2);
      return result;
    },
  },
  {
    name: 'case 33 two hours',
    test(c, run, out) {
      const file = path.join(out, 'long.txt.gz');
      const made = spawnSync(process.execPath, [MAKE_SYNTHETIC, '--long', file, '--minutes', '120'], { encoding: 'utf8' });
      c.equal('make_synthetic.js exit code', made.status, 0);
      const { code, result } = run('long', [file]);
      c.equal('exit code', code, 0);
      const { report } = result;
      c.equal('stretch rates', report.stretches.map((s) => s.rateUhz), [RATE_UHZ]);
      c.equal('readings', report.readings, 823185);
      c.equal('tremor windows', report.windowsByCode[0], 204);
      c.ok(
        `load and draw take ${Math.round(result.loadMs + result.drawMs)} ms, under ${DRAW_LIMIT_MS} ms`,
        result.loadMs + result.drawMs < DRAW_LIMIT_MS,
      );
      return result;
    },
  },
  {
    name: 'case 34 record with the fake watch_cli.py',
    test(c, run, out) {
      const folder = path.join(out, 'recordings');
      fs.rmSync(folder, { recursive: true, force: true });
      const { code, result } = run('record_fake', ['--record-for', '2'], {
        TREMOR_PYTHON: writeFakePython(out),
        TREMOR_RECORDINGS: folder,
        FAKE_WATCH_CLI: JSON.stringify({ copy: SYNTHETIC }),
      });
      c.equal('exit code', code, 0);
      const { recording, report } = result;
      c.equal('recording exit code', recording.exitCode, 0);
      c.equal('recording folder', path.dirname(recording.file), folder);
      const name = path.basename(recording.file);
      c.ok(`the name ${name} has the form tremor-YYYY-MM-DD-HHMMSS.txt.gz`, RECORDING_NAME.test(name));
      c.equal('files in the folder', fs.readdirSync(folder), [name]);
      c.equal('boot', report.bootId, 305419896);
      c.equal('readings', report.readings, 18260);
      c.ok(
        `the record status ${JSON.stringify(report.recordStatus)} starts with "Saved "`,
        report.recordStatus.startsWith('Saved '),
      );
      return result;
    },
  },
  {
    name: 'case 35 record with no Python',
    test(c, run, out) {
      const folder = newFolder(path.join(out, 'recordings_none'));
      const { code, result, hasPng } = run('record_missing', ['--record-for', '2'], {
        TREMOR_PYTHON: path.join(out, 'no-such-python'),
        TREMOR_RECORDINGS: folder,
      });
      c.equal('exit code', code, 1);
      c.ok('the message names TREMOR_PYTHON', result && /TREMOR_PYTHON/.test(result.message));
      c.ok('the PNG exists', hasPng);
      c.equal('files in the folder', fs.readdirSync(folder), []);
      return result;
    },
  },
];

function timing(result) {
  if (!result || typeof result.drawMs !== 'number') {
    return '';
  }
  return `, load ${Math.round(result.loadMs)} ms, draw ${Math.round(result.drawMs)} ms, total ${Math.round(result.totalMs)} ms`;
}

function main() {
  const out = outFolder(process.argv.slice(2));
  console.log(`smoke output in ${out}`);
  const run = (name, appArgs, env) => runApp(out, name, appArgs, env);
  let failed = 0;
  for (const smokeCase of CASES) {
    const c = checker();
    let result = null;
    try {
      result = smokeCase.test(c, run, out);
    } catch (err) {
      c.failures.push(`the JSON could not be checked: ${err.message}`);
    }
    if (c.failures.length === 0) {
      console.log(`pass ${smokeCase.name}${timing(result)}`);
    } else {
      failed++;
      console.log(`FAIL ${smokeCase.name}: ${c.failures.join('; ')}`);
    }
  }
  console.log(`${CASES.length - failed} of ${CASES.length} cases passed`);
  return failed === 0 ? 0 : 1;
}

process.exitCode = main();
