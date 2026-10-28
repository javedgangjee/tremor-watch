'use strict';

// Runs the viewer with no person: open FILE, wait until the page has drawn,
// save the window as a PNG with a JSON report beside it, and give the exit
// code. Exit code 0 means the file was drawn, 1 that it could not be read,
// and 2 that nothing was drawn within the limit.

const fs = require('node:fs');
const { performance } = require('node:perf_hooks');
const { ipcMain } = require('electron');
const { sampleCells } = require('./lib/pixels');

const DRAW_LIMIT_MS = 60000;
// The face's Tremor navy, LOOK_TREMOR in core/look.h.
const NAVY = '#1B2E42';
// The time a window shown for the fallback capture gets to paint.
const SHOW_PAINT_MS = 500;

function waitForDrawn(isOwnPage) {
  return new Promise((resolve) => {
    const listener = (event, report) => {
      if (isOwnPage(event)) {
        ipcMain.removeListener('viewer:drawn', listener);
        resolve(report);
      }
    };
    ipcMain.on('viewer:drawn', listener);
  });
}

/** Resolve with the promise's value, or with null after ms. */
function withLimit(promise, ms) {
  let timer;
  const limit = new Promise((resolve) => {
    timer = setTimeout(() => resolve(null), ms);
  });
  return Promise.race([promise, limit]).finally(() => clearTimeout(timer));
}

/**
 * Capture the window. On macOS a hidden window can give an empty image, so the
 * window is then shown, without focus, and captured again.
 */
async function grab(win) {
  let image = await win.webContents.capturePage();
  let shownWindow = false;
  if (image.isEmpty()) {
    win.showInactive();
    await new Promise((resolve) => setTimeout(resolve, SHOW_PAINT_MS));
    image = await win.webContents.capturePage();
    shownWindow = true;
  }
  const scaleFactor = Math.max(1, ...image.getScaleFactors());
  return { image, scaleFactor, shownWindow };
}

function checkTremorCells(win, image, scaleFactor, cells) {
  const { width, height } = image.getSize(scaleFactor);
  const scale = width / win.getContentSize()[0];
  return sampleCells(image.toBitmap({ scaleFactor }), width, height, scale, cells, NAVY);
}

function jsonPath(pngPath) {
  return pngPath.endsWith('.png') ? `${pngPath.slice(0, -4)}.json` : `${pngPath}.json`;
}

function writeJson(pngPath, result) {
  fs.writeFileSync(jsonPath(pngPath), `${JSON.stringify(result, null, 2)}\n`);
}

/**
 * Run one capture and return the exit code.
 *
 * @param {{win: object, args: {file: string, capture: string}, open: () => {message: object, loadMs: number}, isOwnPage: (event: object) => boolean}} run
 * @returns {Promise<number>}
 */
async function runCapture({ win, args, open, isOwnPage }) {
  const drawn = waitForDrawn(isOwnPage);
  const started = performance.now();
  const { message, loadMs } = open();
  const report = await withLimit(drawn, DRAW_LIMIT_MS);
  if (report === null) {
    const text = `Nothing was drawn within ${DRAW_LIMIT_MS / 1000} seconds.`;
    console.error(text);
    writeJson(args.capture, { file: args.file, exitCode: 2, message: text, loadMs });
    return 2;
  }
  const totalMs = performance.now() - started;
  const { image, scaleFactor, shownWindow } = await grab(win);
  fs.writeFileSync(args.capture, image.toPNG({ scaleFactor }));
  const [pageHasRequire, pageHasProcess] = await win.webContents.executeJavaScript(
    "[typeof require !== 'undefined', typeof process !== 'undefined']",
  );
  const exitCode = message.ok ? 0 : 1;
  if (!message.ok) {
    console.error(message.message);
  }
  writeJson(args.capture, {
    file: args.file,
    exitCode,
    message: message.ok ? null : message.message,
    report,
    loadMs,
    drawMs: report.drawMs ?? null,
    totalMs,
    shownWindow,
    webPreferences: win.webContents.getLastWebPreferences(),
    pageHasRequire,
    pageHasProcess,
    tremorCellPixels: message.ok ? checkTremorCells(win, image, scaleFactor, report.tremorCells) : null,
  });
  return exitCode;
}

module.exports = { runCapture };
