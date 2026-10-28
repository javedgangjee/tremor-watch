'use strict';

const path = require('node:path');

const REPO = path.join(__dirname, '..', '..', '..');
const VIEWER = path.join(REPO, 'viewer');

module.exports = {
  REPO,
  VIEWER,
  FORMAT_DOC: path.join(REPO, 'core', 'recording_format.md'),
  SYNTHETIC: path.join(VIEWER, 'test', 'fixtures', 'synthetic.txt.gz'),
  log: (name) => path.join(REPO, 'tests', 'firmware', `${name}.txt.gz`),
};
