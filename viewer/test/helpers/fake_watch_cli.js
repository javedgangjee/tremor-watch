'use strict';

// A stand-in for `tools/watch_cli.py record --out FILE` in the recorder's
// tests, so no test needs the watch or pyserial. It finds `--out FILE`
// anywhere in its arguments, so it also runs behind a shell script that
// passes the watch_cli.py path first. It reads its orders from the
// environment variable FAKE_WATCH_CLI as JSON, with these fields.
//
//   argsOut       a file for its arguments and PYTHONUNBUFFERED as JSON
//   startLines    lines for the standard error after the first line
//   dieWith       an exit code: write only startLines, make no file, and exit
//   ignoreInt     true to ignore SIGINT
//   closeDelayMs  a wait between SIGINT and the exit
//   copy          a gzip file whose bytes go to FILE at SIGINT
//   stopLines     lines written at SIGINT, before the "Saved" line
//   exitCode      the exit code at SIGINT, 0 by default
//   sigintOut     a file that gains one line for each SIGINT

const fs = require('node:fs');
const zlib = require('node:zlib');

// The text FILE holds when no copy is given.
const FAKE_LINES = ['0.000\tfake line 1', '0.010\tfake line 2', '0.020\tfake line 3'];

// Synchronous writes, so no line is lost when the process exits.
const say = (line) => fs.writeSync(2, `${line}\n`);

function main() {
  const orders = JSON.parse(process.env.FAKE_WATCH_CLI || '{}');
  const args = process.argv.slice(1);
  if (orders.argsOut) {
    fs.writeFileSync(orders.argsOut, JSON.stringify({ args, PYTHONUNBUFFERED: process.env.PYTHONUNBUFFERED }));
  }
  const startLines = orders.startLines ?? [];
  if (orders.dieWith !== undefined) {
    startLines.forEach(say);
    process.exit(orders.dieWith);
  }
  const outAt = args.indexOf('--out');
  const file = outAt === -1 ? undefined : args[outAt + 1];
  if (file === undefined) {
    say('the following arguments are required: --out');
    process.exit(2);
  }
  if (fs.existsSync(file)) {
    say(`${file} exists already. The tool does not write over a saved recording.`);
    process.exit(1);
  }
  // watch_cli.py makes the file before it starts to save lines.
  fs.writeFileSync(file, '', { flag: 'wx' });

  let stopping = false;
  process.on('SIGINT', () => {
    if (orders.sigintOut) {
      fs.appendFileSync(orders.sigintOut, 'SIGINT\n');
    }
    if (orders.ignoreInt || stopping) {
      return;
    }
    stopping = true;
    setTimeout(() => {
      const bytes = orders.copy ? fs.readFileSync(orders.copy) : zlib.gzipSync(`${FAKE_LINES.join('\n')}\n`);
      fs.writeFileSync(file, bytes);
      const count = zlib.gunzipSync(bytes).toString('utf8').split('\n').filter((line) => line !== '').length;
      say('The recording was stopped.');
      (orders.stopLines ?? []).forEach(say);
      say(`Saved ${count} lines to ${file}.`);
      process.exit(orders.exitCode ?? 0);
    }, orders.closeDelayMs ?? 0);
  });
  // The handler is in place, so a test may now send SIGINT.
  say(`Saving the recording to ${file}. Press Ctrl-C to stop.`);
  startLines.forEach(say);
  // Keep running until a signal ends the run.
  setInterval(() => {}, 1 << 30);
}

if (require.main === module) {
  main();
}

module.exports = { FAKE_LINES };
