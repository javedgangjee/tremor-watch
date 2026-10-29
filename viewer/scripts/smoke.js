'use strict';

// Runs the real app in capture mode on the cases of check 2 in
// specs/features/12-recording-viewer/validation.md,
// specs/features/14-record-button/validation.md, and
// specs/features/15-viewer-redesign/validation.md, prints one line per case,
// and exits with code 1 when a case fails. It needs the installed packages and
// a logged-in screen. The record cases run test/helpers/fake_watch_cli.js in
// place of watch_cli.py, so they need no watch. Every case runs with
// --theme light unless it names a theme.
//
//   npm --prefix viewer run smoke -- [--out DIR]

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const electron = require('electron');
const { BOOT_B, RATE_UHZ, HASH } = require('../test/helpers/synthetic');
const { startText } = require('../src/lib/title');
const { loadRecording } = require('../src/lib/load');
const C = require('../src/lib/chart');

const VIEWER = path.join(__dirname, '..');
const REPO = path.join(VIEWER, '..');
const SYNTHETIC = path.join(VIEWER, 'test', 'fixtures', 'synthetic.txt.gz');
const MAKE_SYNTHETIC = path.join(__dirname, 'make_synthetic.js');
const FAKE_WATCH_CLI = path.join(VIEWER, 'test', 'helpers', 'fake_watch_cli.js');
const RECORDING_NAME = /^tremor-\d{4}-\d{2}-\d{2}-\d{6}\.txt\.gz$/;
const log = (name) => path.join(REPO, 'tests', 'firmware', `${name}.txt.gz`);
const CASE_LIMIT_MS = 90000;
const DRAW_LIMIT_MS = 10000;
// The --ink colours of colors.css, which fill the tremor blocks.
const INK_LIGHT = '#16181D';
const INK_DARK = '#F4F7FA';
const FONT_FAMILIES = ['Red Hat Display', 'Libre Franklin', 'IBM Plex Mono'];
// The tremor line width in page pixels, the room allowed for rounding, and
// the share of a selection line that its dashes fill.
const TREMOR_LINE_PX = 2;
const WIDTH_SLACK_PX = 0.5;
const PLACE_SLACK_PX = 1;
const TIME_SLACK_S = 1e-6;
const DASH_SHARE = [0.25, 0.75];
// Window 105 of stretch 0 of boot A, a no tremor window away from both episodes.
const SELECT = '0,105';
const SELECT_SPAN = [105.25, 109.25];

/** The episodes and the full y range of boot A of the made-up recording. */
const bootA = (() => {
  let found = null;
  return () => {
    if (found === null) {
      const b = loadRecording(SYNTHETIC).boots.find((x) => x.id === 305419896);
      found = { spans: b.tremorSpans, range: C.sharedRange([b.gx, b.gy, b.gz], 0, b.timeS.length - 1) };
    }
    return found;
  };
})();

const nearAll = (a, b, slack) => a.length === b.length && a.every((v, i) => Math.abs(v - b[i]) <= slack);

/**
 * Check that each line of each chart sits within 1 page pixel of where the
 * chart puts its time, and that its times are the wanted ones.
 */
function checkLines(c, what, report, lists, wantTimes, widthPx) {
  c.equal(`${what} charts`, lists.length, report.plotEdges.length);
  lists.forEach((lines, i) => {
    const times = lines.map((l) => l.t);
    c.ok(`${what} of chart ${i} are at ${JSON.stringify(times)}, not ${JSON.stringify(wantTimes)}`, nearAll(times, wantTimes, TIME_SLACK_S));
    const edges = report.plotEdges[i];
    for (const line of lines) {
      const want = edges.left + C.xAt(line.t, report.view, edges.right - edges.left);
      const at = line.x + line.width / 2;
      c.ok(`the ${what} line at ${line.t} of chart ${i} is at ${at}, not within 1 px of ${want}`, Math.abs(at - want) <= PLACE_SLACK_PX);
      if (widthPx !== null) {
        c.ok(`the ${what} line at ${line.t} of chart ${i} is ${line.width} px wide`, Math.abs(line.width - widthPx) <= WIDTH_SLACK_PX);
      }
    }
  });
}

/** Check the tremor lines of every chart against the episodes of boot A and their pixels. */
function checkTremorLines(c, result, charts) {
  const { report } = result;
  const want = C.edgesInView(bootA().spans, report.view);
  c.ok(`the episodes of boot A give the four times, not ${JSON.stringify(want)}`, want.length === 4);
  c.equal('tremor line charts', report.tremorLines.length, charts);
  checkLines(c, 'tremor lines', report, report.tremorLines, want, TREMOR_LINE_PX);
  const pixels = result.tremorLinePixels;
  c.equal('tremor line pixels', [pixels.checked, pixels.matched], [12 * charts, 12 * charts]);
}

/**
 * Check that each chart shades each episode of boot A in view, from where it
 * puts the episode's start to where it puts its end, within 1 page pixel.
 */
function checkBands(c, report, charts) {
  const view = report.view;
  const want = bootA().spans.filter(([a, b]) => b > view.min && a < view.max);
  c.equal('tremor band charts', report.tremorBands.length, charts);
  report.tremorBands.forEach((bands, i) => {
    c.equal(`tremor bands of chart ${i}`, bands.length, want.length);
    const edges = report.plotEdges[i];
    const xOf = (t) => edges.left + C.xAt(Math.min(Math.max(t, view.min), view.max), view, edges.right - edges.left);
    bands.forEach((band, k) => {
      if (k >= want.length) {
        return;
      }
      const [a, b] = want[k];
      c.ok(`band ${k} of chart ${i} starts at ${band.x}, not within 1 px of ${xOf(a)}`, Math.abs(band.x - xOf(a)) <= PLACE_SLACK_PX);
      const right = band.x + band.width;
      c.ok(`band ${k} of chart ${i} ends at ${right}, not within 1 px of ${xOf(b)}`, Math.abs(right - xOf(b)) <= PLACE_SLACK_PX);
    });
  });
}

/** Check that each chart has the range of boot A. */
function checkRangeOfBootA(c, report, charts) {
  c.equal('y range charts', report.yRanges.length, charts);
  report.yRanges.forEach((range, i) => {
    c.ok(`the y range of chart ${i} is ${JSON.stringify(range)}, not the range of boot A`, nearAll(range, bootA().range, TIME_SLACK_S));
  });
}

/** Check that the stacked charts share one y range and one list of at least two y labels. */
function checkSharedY(c, report) {
  c.equal('y range charts', report.yRanges.length, 3);
  c.ok(`the y ranges ${JSON.stringify(report.yRanges)} are equal`, report.yRanges.every((r) => nearAll(r, report.yRanges[0], 0)));
  c.equal('y tick lists', report.yTicks.length, 3);
  c.ok(`the y ticks ${JSON.stringify(report.yTicks)} are equal`, report.yTicks.every((t) => JSON.stringify(t) === JSON.stringify(report.yTicks[0])));
  c.ok(`the first chart has ${report.yTicks[0].length} y labels, at least 2`, report.yTicks[0].length >= 2);
}

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
  const theme = appArgs.includes('--theme') ? [] : ['--theme', 'light'];
  const run = spawnSync(electron, [VIEWER, ...appArgs, ...theme, '--capture', png], {
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

/** Check that the page loaded the three fonts and that the Answer row lines up with the chart. */
function checkFontsAndRow(c, report) {
  for (const family of FONT_FAMILIES) {
    c.ok(`fontsLoaded holds ${family}`, report.fontsLoaded.includes(family));
  }
  c.ok(`rowAlignPx is ${report.rowAlignPx}, at most 1`, typeof report.rowAlignPx === 'number' && report.rowAlignPx <= 1);
}

/** Make the two hour recording of case 33 unless it exists, and give its path. */
function longFile(c, out) {
  const file = path.join(out, 'long.txt.gz');
  if (!fs.existsSync(file)) {
    const made = spawnSync(process.execPath, [MAKE_SYNTHETIC, '--long', file, '--minutes', '120'], { encoding: 'utf8' });
    c.equal('make_synthetic.js exit code', made.status, 0);
  }
  return file;
}

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
      c.equal('tremor colour', result.tremorColour, INK_LIGHT);
      c.equal('theme', report.theme, 'light');
      c.equal('layout', report.layout, 'overlaid');
      c.equal('shown axes', report.shownAxes, ['x', 'y', 'z']);
      c.equal('plot heights', report.plotHeights, [340]);
      c.equal('time span', report.span, 'all');
      c.equal('start text', report.startText, null);
      c.equal('selection', report.selection, null);
      checkFontsAndRow(c, report);
      checkTremorLines(c, result, 1);
      checkBands(c, report, 1);
      c.equal('selection lines', report.selectionLines, [[]]);
      c.equal('selection line pixels sampled', result.selectionLinePixels.sampled, 0);
      checkRangeOfBootA(c, report, 1);
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
      fs.rmSync(file, { force: true });
      const { code, result } = run('long', [longFile(c, out)]);
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
        `the outcome text ${JSON.stringify(recording.text)} starts with "Saved "`,
        recording.text.startsWith('Saved '),
      );
      c.equal('record status', report.recordStatus, '');
      c.ok('the start text is not null', report.startText !== null);
      c.equal('start text', report.startText, startText(name, []));
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
  {
    name: 'case 15 of feature 15 dark theme',
    test(c, run) {
      const { code, result } = run('synthetic_dark', [SYNTHETIC, '--theme', 'dark']);
      c.equal('exit code', code, 0);
      const { report } = result;
      c.equal('theme', report.theme, 'dark');
      c.equal('tremor colour', result.tremorColour, INK_DARK);
      c.equal('tremor cell pixels', [result.tremorCellPixels.checked, result.tremorCellPixels.matched], [39, 39]);
      checkFontsAndRow(c, report);
      const pixels = result.tremorLinePixels;
      c.equal('tremor line pixels against INK dark', [pixels.checked, pixels.matched], [12, 12]);
      return result;
    },
  },
  {
    name: 'case 16 of feature 15 stacked layout',
    test(c, run) {
      const { code, result } = run('synthetic_stacked', [SYNTHETIC, '--layout', 'stacked']);
      c.equal('exit code', code, 0);
      const { report } = result;
      c.equal('layout', report.layout, 'stacked');
      c.equal('shown axes', report.shownAxes, ['x', 'y', 'z']);
      c.equal('plot heights', report.plotHeights, [120, 120, 120]);
      c.equal('tremor colour', result.tremorColour, INK_LIGHT);
      c.equal('tremor cell pixels', [result.tremorCellPixels.checked, result.tremorCellPixels.matched], [39, 39]);
      c.ok(`rowAlignPx is ${report.rowAlignPx}, at most 1`, typeof report.rowAlignPx === 'number' && report.rowAlignPx <= 1);
      checkTremorLines(c, result, 3);
      checkBands(c, report, 3);
      checkRangeOfBootA(c, report, 3);
      checkSharedY(c, report);
      return result;
    },
  },
  {
    name: 'case 17 of feature 15 two hours stacked',
    test(c, run, out) {
      const { code, result } = run('long_stacked', [longFile(c, out), '--layout', 'stacked']);
      c.equal('exit code', code, 0);
      const { report } = result;
      c.equal('readings', report.readings, 823185);
      c.equal('tremor windows', report.windowsByCode[0], 204);
      c.equal('plot heights', report.plotHeights, [120, 120, 120]);
      c.ok(
        `load and draw take ${Math.round(result.loadMs + result.drawMs)} ms, under ${DRAW_LIMIT_MS} ms`,
        result.loadMs + result.drawMs < DRAW_LIMIT_MS,
      );
      checkSharedY(c, report);
      return result;
    },
  },
  {
    name: 'case 18 of feature 15 boot with no readings',
    test(c, run, out) {
      const file = path.join(out, 'noreadings.txt');
      const lines = [
        `B,1,11,12,${HASH}`,
        'S,0,0,1000,114330200,1024',
        'W,0,0,3,0.5,10,5',
        `B,2,11,12,${HASH}`,
        'S,0,0,1000,114330200,1024',
        'T,0,2,1000',
        'R,0,32,-32,64,0,0,4096',
        'R,1,0,0,0,0,0,4096',
      ];
      fs.writeFileSync(file, lines.map((line, i) => `${(i / 1000).toFixed(3)}\t${line}\n`).join(''));
      const { code, result } = run('noreadings', [file, '--boot', '1']);
      c.equal('exit code', code, 0);
      const { report } = result;
      c.equal('readings', report.readings, 0);
      c.equal('plot heights', report.plotHeights, []);
      c.equal('tremor cells', report.tremorCells.length, 0);
      c.equal('windows of codes 0 to 3', codes(report, [0, 1, 2, 3]), [0, 0, 0, 1]);
      c.equal('tremor lines', report.tremorLines, []);
      c.equal('tremor bands', report.tremorBands, []);
      c.equal('time span', report.span, null);
      c.equal('selection lines', report.selectionLines, []);
      c.equal('y ranges', report.yRanges, null);
      return result;
    },
  },
  {
    name: 'case 24 of feature 15 selection lines',
    test(c, run) {
      const { code, result, hasPng } = run('selected', [SYNTHETIC], { TREMOR_CAPTURE_SELECT: SELECT });
      c.equal('exit code', code, 0);
      c.ok('selected.png exists', hasPng);
      const { report } = result;
      c.equal('selection', report.selection, { stretch: 0, window: 105, code: 1 });
      c.equal('selection line charts', report.selectionLines.length, 1);
      checkLines(c, 'selection lines', report, report.selectionLines, SELECT_SPAN, null);
      const lines = result.selectionLinePixels;
      c.equal('selection lines drawn', lines.lines, 2);
      c.equal('selection line pixels in the tremor colour', lines.tremorColour, 0);
      const share = lines.sampled > 0 ? lines.lineColour / lines.sampled : 0;
      c.ok(
        `the dashes fill ${share.toFixed(3)} of the selection lines, from ${DASH_SHARE[0]} to ${DASH_SHARE[1]}`,
        share >= DASH_SHARE[0] && share <= DASH_SHARE[1],
      );
      const pixels = result.tremorLinePixels;
      c.equal('tremor line pixels', [pixels.checked, pixels.matched], [12, 12]);
      const bad = run('selected_bad', [SYNTHETIC], { TREMOR_CAPTURE_SELECT: 'abc' });
      c.equal('exit code for TREMOR_CAPTURE_SELECT abc', bad.code, 2);
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
