'use strict';

// Writes the made-up recording to viewer/test/fixtures/synthetic.txt.gz, or
// with --long OUT --minutes M a long recording to OUT.
//
//   node viewer/scripts/make_synthetic.js
//   node viewer/scripts/make_synthetic.js --long OUT.txt.gz --minutes 120

const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const { buildSyntheticText, buildLongText } = require('../test/helpers/synthetic');

const FIXTURE = path.join(__dirname, '..', 'test', 'fixtures', 'synthetic.txt.gz');
const USAGE = 'node viewer/scripts/make_synthetic.js [--long OUT --minutes M]';

function readOptions(argv) {
  if (argv.length === 0) {
    return { out: FIXTURE, text: buildSyntheticText };
  }
  const options = {};
  for (let i = 0; i < argv.length; i += 2) {
    if (!['--long', '--minutes'].includes(argv[i]) || argv[i + 1] === undefined) {
      return null;
    }
    options[argv[i]] = argv[i + 1];
  }
  const minutes = Number(options['--minutes']);
  if (!options['--long'] || !(minutes > 0)) {
    return null;
  }
  return { out: path.resolve(options['--long']), text: () => buildLongText(minutes) };
}

function main() {
  const options = readOptions(process.argv.slice(2));
  if (options === null) {
    console.error(`Usage: ${USAGE}`);
    return 2;
  }
  // zlib writes an mtime of 0, so the same text gives the same bytes.
  fs.writeFileSync(options.out, zlib.gzipSync(options.text(), { level: 9 }));
  console.log(`wrote ${options.out}`);
  return 0;
}

process.exitCode = main();
