'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { VIEWER } = require('./helpers/paths');

const read = (...parts) => fs.readFileSync(path.join(VIEWER, ...parts), 'utf8');

/** Every file under a folder of viewer/, without node_modules. */
function filesIn(folder) {
  const found = [];
  for (const entry of fs.readdirSync(path.join(VIEWER, folder), { withFileTypes: true })) {
    const rel = path.join(folder, entry.name);
    if (entry.name === 'node_modules') {
      continue;
    }
    if (entry.isDirectory()) {
      found.push(...filesIn(rel));
    } else {
      found.push(rel);
    }
  }
  return found;
}

test('case 25: the two packages and their exact versions', () => {
  const pkg = JSON.parse(read('package.json'));
  assert.deepEqual(pkg.dependencies, { uplot: '1.6.32' });
  assert.deepEqual(pkg.devDependencies, { electron: '44.7.1' });
  const lock = JSON.parse(read('package-lock.json'));
  assert.equal(lock.lockfileVersion, 3);
  assert.equal(lock.packages['node_modules/uplot'].version, '1.6.32');
  assert.equal(lock.packages['node_modules/electron'].version, '44.7.1');
});

test('case 26: module limits, no port, no remote content, security settings, and no dashes', () => {
  for (const file of filesIn('src/lib')) {
    for (const [, name] of read(file).matchAll(/require\(\s*['"]([^'"]+)['"]\s*\)/g)) {
      assert.ok(name.startsWith('node:') || name.startsWith('./'), `${file} requires ${name}`);
    }
  }
  for (const file of [...filesIn('src'), ...filesIn('scripts')]) {
    for (const word of ['serialport', '/dev/cu', '/dev/tty']) {
      assert.ok(!read(file).includes(word), `${file} holds ${word}`);
    }
  }
  for (const file of filesIn('src/renderer')) {
    assert.ok(!/https?:/.test(read(file)), `${file} holds a web address`);
  }

  const csp = /http-equiv="Content-Security-Policy" content="([^"]*)"/.exec(read('src', 'renderer', 'index.html'));
  assert.equal(
    csp[1],
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'",
  );

  const main = read('src', 'main.js');
  for (const setting of ['contextIsolation: true', 'nodeIntegration: false', 'sandbox: true', 'webSecurity: true']) {
    assert.ok(main.includes(setting), setting);
  }

  const textFiles = ['package.json', 'package-lock.json', '.npmrc', ...filesIn('src'), ...filesIn('scripts'), ...filesIn('test')];
  for (const file of textFiles.filter((f) => !f.endsWith('.gz'))) {
    assert.ok(!/[\u2013\u2014]/.test(read(file)), `${file} holds an em dash or an en dash`);
  }
});
