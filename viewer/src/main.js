'use strict';

// The viewer's main process. It owns the window, the menu, the open dialog,
// the file reading, and the recorder. It never opens the watch's port, and
// the Record button runs tools/watch_cli.py record through lib/recorder.js.

const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { performance } = require('node:perf_hooks');
const { app, BrowserWindow, Menu, dialog, ipcMain, nativeTheme, session } = require('electron');
const { ArgsError, RecordError, RecordingError } = require('./lib/errors');
const { parseArgs, captureSelect, USAGE } = require('./lib/args');
const { loadRecording } = require('./lib/load');
const { Recorder, recorderSettings } = require('./lib/recorder');
const { runCapture } = require('./capture');

const PAGE = path.join(__dirname, 'renderer', 'index.html');
const PAGE_URL = pathToFileURL(PAGE).href;
// The --surface-page colour of the page's light and dark themes, from
// viewer/src/renderer/design/colors.css, so the window shows no flash.
const PAGE_BACKGROUND = { light: '#F6F7F9', dark: '#16181D' };

const recorder = new Recorder(
  recorderSettings({ env: process.env, home: os.homedir(), cwd: process.env.INIT_CWD || process.cwd() }),
);
// Set when a quit waits for a recording to stop, so its file is not opened.
let quitting = false;

function readArgs() {
  try {
    // `electron .` leaves the app's own arguments after the first two.
    const args = parseArgs(process.argv.slice(2), process.env.INIT_CWD || process.cwd());
    // A test hook for capture mode only: the window the page selects before it reports.
    args.select = args.capture === null ? null : captureSelect(process.env);
    return args;
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
 * A layout given here is the one the page starts the file with, and a select
 * given here is the window the page selects before it reports. Returns the
 * message and the time the load took.
 */
function openRecording(win, filePath, bootId = null, layout = null, select = null) {
  const started = performance.now();
  let message;
  try {
    const recording = loadRecording(filePath);
    if (bootId !== null && !recording.boots.some((b) => b.id === bootId)) {
      const ids = recording.boots.map((b) => b.id).join(', ');
      throw new RecordingError(`${recording.fileName} holds no boot ${bootId}. Its boots are ${ids}.`);
    }
    message = { ok: true, recording, bootId };
    if (layout !== null) {
      message.layout = layout;
    }
    if (select !== null) {
      message.select = select;
    }
  } catch (err) {
    const text = err instanceof RecordingError ? err.message : `Could not open ${filePath}: ${err.message}`;
    message = { ok: false, file: filePath, message: text };
  }
  const loadMs = performance.now() - started;
  win.webContents.send('viewer:recording', message);
  return { message, loadMs };
}

/** Send the page the reason a recording cannot be shown. */
function showFailure(win, filePath, text) {
  const message = { ok: false, file: filePath, message: text };
  win.webContents.send('viewer:recording', message);
  return { message, loadMs: 0 };
}

function sendRecordStatus(win, status) {
  if (!win.isDestroyed() && !win.webContents.isDestroyed()) {
    win.webContents.send('viewer:record-status', status);
  }
}

/**
 * Start a recording for the button or capture mode. Returns null when it
 * started, or the status that says why it did not. The page is sent that
 * status unless a recording runs, whose own status it keeps showing.
 */
function startRecording(win) {
  try {
    recorder.start();
    return null;
  } catch (err) {
    if (!(err instanceof RecordError)) {
      throw err;
    }
    const status = { state: 'idle', startedAt: null, file: null, text: err.message, ok: false };
    if (recorder.state === 'idle') {
      sendRecordStatus(win, status);
    }
    return status;
  }
}

/** Stop the recording. The promise gives the outcome, or null when none ran. */
function stopRecording() {
  return recorder.stop();
}

/**
 * Capture mode's --record-for: record through the same two functions as the
 * button, stop after the given seconds unless the recording ended first, and
 * open the file or send the page why it cannot be shown.
 */
async function recordThenOpen(win, seconds, bootId) {
  const refused = startRecording(win);
  if (refused !== null) {
    const recording = { file: null, exitCode: null, signal: null, text: refused.text };
    return { ...showFailure(win, null, refused.text), recording };
  }
  const outcome = await new Promise((resolve) => {
    const timer = setTimeout(stopRecording, seconds * 1000);
    recorder.once('done', (ended) => {
      clearTimeout(timer);
      resolve(ended);
    });
  });
  const recording = { file: outcome.file, exitCode: outcome.code, signal: outcome.signal, text: outcome.text };
  const opened = outcome.open ? openRecording(win, outcome.file, bootId) : showFailure(win, outcome.file, outcome.text);
  return { ...opened, recording };
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
    backgroundColor: nativeTheme.shouldUseDarkColors ? PAGE_BACKGROUND.dark : PAGE_BACKGROUND.light,
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
  nativeTheme.themeSource = args.theme;
  const win = createWindow(args.capture !== null);
  lockDown(win);
  setMenu(win);
  ipcMain.on('viewer:open', (event) => {
    if (isOwnPage(win, event)) {
      chooseRecording(win);
    }
  });
  ipcMain.on('viewer:record-start', (event) => {
    if (isOwnPage(win, event)) {
      startRecording(win);
    }
  });
  ipcMain.on('viewer:record-stop', (event) => {
    if (isOwnPage(win, event)) {
      stopRecording();
    }
  });
  recorder.on('status', (status) => sendRecordStatus(win, status));
  // In capture mode recordThenOpen() opens the file itself.
  recorder.on('done', (outcome) => {
    if (outcome.open && !quitting && args.capture === null && !win.isDestroyed()) {
      openRecording(win, outcome.file);
    }
  });
  await win.loadFile(PAGE);
  if (args.capture !== null) {
    let code;
    try {
      code = await runCapture({
        win,
        args,
        open: args.recordFor === null
          ? () => openRecording(win, args.file, args.bootId, args.layout, args.select)
          : () => recordThenOpen(win, args.recordFor, args.bootId),
        isOwnPage: (event) => isOwnPage(win, event),
      });
    } finally {
      await stopRecording();
    }
    app.exit(code);
  } else if (args.file !== null) {
    openRecording(win, args.file, args.bootId, args.layout);
  }
}

app.on('window-all-closed', () => app.quit());

// Closing the window and Cmd+Q both come here. A running recording holds the
// quit until watch_cli.py has closed its file, and its file is not opened.
app.on('before-quit', (event) => {
  if (recorder.state === 'idle') {
    return;
  }
  event.preventDefault();
  if (!quitting) {
    quitting = true;
    stopRecording().then(() => app.quit());
  }
});

// A failure here means the page was never drawn, which capture mode reports
// with exit code 2. A running recording is stopped first.
start().catch((err) => {
  console.error(err);
  stopRecording().then(() => app.exit(2));
});
