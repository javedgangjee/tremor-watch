'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

/** Make a temporary folder for one test file, removed when the process ends. */
function tempFolder() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'tremor-viewer-'));
  process.on('exit', () => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

module.exports = { tempFolder };
