'use strict';

// The viewer's main process. It owns the window, the menu, the open dialog,
// and the file reading, and it never opens the watch's port.

const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { performance } = require('node:perf_hooks');
const { app, BrowserWindow, Menu, dialog, ipcMain, session } = require('electron');
const { ArgsError, RecordingError } = require('./lib/errors');
const { parseArgs, USAGE } = require('./lib/args');
const { loadRecording } = require('./lib/load');
const { runCapture } = require('./capture');

const PAGE = path.join(__dirname, 'renderer', 'index.html');
const PAGE_URL = pathToFileURL(PAGE).href;

function readArgs() {
  try {
    // `electron .` leaves the app's own arguments after the first two.
    return parseArgs(process.argv.slice(2), process.env.INIT_CWD || process.cwd());
  } catch (err) {
    if (!(err instanceof ArgsError)) {
      throw err;
    }
    console.error(err.message);
    console.error(`Usage: ${USAGE}`);
    process.exit(2);
  }
}

/** True when an IPC message comes from the viewer's own page in its window. */
function isOwnPage(win, event) {
  return event.sender === win.webContents && event.senderFrame !== null && event.senderFrame.url === PAGE_URL;
}

/**
 * Load a recording and send it, or the reason it cannot be shown, to the page.
 * Returns the message and the time the load took.
 */
function openRecording(win, filePath, bootId = null) {
  const started = performance.now();
  let message;
  try {
    const recording = loadRecording(filePath);
    if (bootId !== null && !recording.boots.some((b) => b.id === bootId)) {
      const ids = recording.boots.map((b) => b.id).join(', ');
      throw new RecordingError(`${recording.fileName} holds no boot ${bootId}. Its boots are ${ids}.`);
    }
    message = { ok: true, recording, bootId };
  } catch (err) {
    const text = err instanceof RecordingError ? err.message : `Could not open ${filePath}: ${err.message}`;
    message = { ok: false, file: filePath, message: text };
  }
  const loadMs = performance.now() - started;
  win.webContents.send('viewer:recording', message);
  return { message, loadMs };
}

async function chooseRecording(win) {
  const result = await dialog.showOpenDialog(win, {
    title: 'Open a recording',
    properties: ['openFile'],
    filters: [{ name: 'Recordings', extensions: ['gz', 'txt'] }],
  });
  if (!result.canceled && result.filePaths.length === 1) {
    openRecording(win, result.filePaths[0]);
  }
}

function setMenu(win) {
  const isMac = process.platform === 'darwin';
  const template = [
    ...(isMac ? [{ role: 'appMenu' }] : []),
    {
      label: 'File',
      submenu: [
        { label: 'Open…', accelerator: 'CmdOrCtrl+O', click: () => chooseRecording(win) },
        { type: 'separator' },
        isMac ? { role: 'close' } : { role: 'quit' },
      ],
    },
    { role: 'editMenu' },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

/** Deny every new window, navigation, and permission request. */
function lockDown(win) {
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  win.webContents.on('will-navigate', (event) => event.preventDefault());
  session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
}

function createWindow(capture) {
  return new BrowserWindow({
    width: 1400,
    height: 860,
    show: !capture,
    title: 'Tremor log viewer',
    backgroundColor: '#F6F3EE',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      paintWhenInitiallyHidden: true,
    },
  });
}

async function start() {
  const args = readArgs();
  await app.whenReady();
  const win = createWindow(args.capture !== null);
  lockDown(win);
  setMenu(win);
  ipcMain.on('viewer:open', (event) => {
    if (isOwnPage(win, event)) {
      chooseRecording(win);
    }
  });
  await win.loadFile(PAGE);
  if (args.capture !== null) {
    const code = await runCapture({
      win,
      args,
      open: () => openRecording(win, args.file, args.bootId),
      isOwnPage: (event) => isOwnPage(win, event),
    });
    app.exit(code);
  } else if (args.file !== null) {
    openRecording(win, args.file, args.bootId);
  }
}

app.on('window-all-closed', () => app.quit());

// A failure here means the page was never drawn, which capture mode reports
// with exit code 2.
start().catch((err) => {
  console.error(err);
  app.exit(2);
});
