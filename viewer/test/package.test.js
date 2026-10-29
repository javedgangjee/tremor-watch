'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
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
  // The font licences in src/renderer/fonts/ hold web addresses, so only the
  // page's own files are checked.
  for (const file of filesIn('src/renderer').filter((f) => /\.(html|css|js)$/.test(f))) {
    assert.ok(!/https?:/.test(read(file)), `${file} holds a web address`);
  }

  const csp = /http-equiv="Content-Security-Policy" content="([^"]*)"/.exec(read('src', 'renderer', 'index.html'));
  assert.equal(
    csp[1],
    "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'",
  );

  const main = read('src', 'main.js');
  for (const setting of ['contextIsolation: true', 'nodeIntegration: false', 'sandbox: true', 'webSecurity: true']) {
    assert.ok(main.includes(setting), setting);
  }

  const textFiles = ['package.json', 'package-lock.json', '.npmrc', ...filesIn('src'), ...filesIn('scripts'), ...filesIn('test')];
  for (const file of textFiles.filter((f) => !f.endsWith('.gz') && !f.endsWith('.woff2'))) {
    assert.ok(!/[\u2013\u2014]/.test(read(file)), `${file} holds an em dash or an en dash`);
  }
});

/** Run preload.js with a stand-in for Electron, and give the API it exposes and the calls it makes. */
function loadPreload() {
  const sent = [];
  const listeners = new Map();
  const exposed = {};
  const electron = {
    contextBridge: {
      exposeInMainWorld: (name, api) => {
        exposed[name] = api;
      },
    },
    ipcRenderer: {
      send: (...args) => sent.push(args),
      on: (channel, listener) => listeners.set(channel, listener),
    },
  };
  const fakeRequire = (name) => {
    assert.equal(name, 'electron');
    return electron;
  };
  vm.runInNewContext(read('src', 'preload.js'), { require: fakeRequire });
  return { api: exposed.viewer, sent, listeners };
}

/** The text of the ipcMain.on handler for a channel in main.js, up to its closing `});`. */
function handlerText(main, channel) {
  const opening = `ipcMain.on('${channel}'`;
  const at = main.indexOf(opening);
  assert.ok(at !== -1, `main.js has no handler for ${channel}`);
  assert.equal(main.indexOf(opening, at + 1), -1, `main.js has two handlers for ${channel}`);
  return main.slice(at, main.indexOf('});', at));
}

test('case 14 of feature 14: the record calls, the IPC checks, and no shell', () => {
  const { api, sent, listeners } = loadPreload();
  assert.deepEqual(Object.keys(api).sort(), [
    'onRecordStatus',
    'onRecording',
    'openFile',
    'reportDrawn',
    'startRecording',
    'stopRecording',
  ]);
  api.startRecording('/etc/passwd');
  api.stopRecording('rm -rf /');
  assert.deepEqual(sent, [['viewer:record-start'], ['viewer:record-stop']]);
  const got = [];
  api.onRecordStatus((...args) => got.push(args));
  const status = { state: 'idle', startedAt: null, file: null, text: 'x', ok: false };
  listeners.get('viewer:record-status')({ sender: 'event' }, status);
  assert.deepEqual(got, [[status]]);

  const main = read('src', 'main.js');
  for (const channel of ['viewer:open', 'viewer:record-start', 'viewer:record-stop']) {
    assert.ok(handlerText(main, channel).includes('isOwnPage(win, event)'), `${channel} does not call isOwnPage()`);
  }

  for (const file of filesIn('src')) {
    const text = read(file);
    for (const word of ['shell: true', 'execSync(']) {
      assert.ok(!text.includes(word), `${file} holds ${word}`);
    }
    // format.js and parse.js call RegExp's exec(), which runs no program, so
    // exec( is looked for only where child_process is required.
    if (text.includes('child_process')) {
      assert.ok(!text.includes('exec('), `${file} holds exec(`);
    }
  }

  const recorder = read('src', 'lib', 'recorder.js');
  for (const [, name] of recorder.matchAll(/require\(\s*['"]([^'"]+)['"]\s*\)/g)) {
    assert.ok(name.startsWith('node:') || name === './errors', `recorder.js requires ${name}`);
  }
});
