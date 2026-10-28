'use strict';

// Runs the viewer with no person: open FILE, or record for --record-for
// seconds and open the new file, wait until the page has drawn, save the
// window as a PNG with a JSON report beside it, and give the exit code. Exit
// code 0 means the file was drawn, 1 that it could not be read or the
// recording failed, and 2 that nothing was drawn within the limit.

const fs = require('node:fs');
const { performance } = require('node:perf_hooks');
const { ipcMain } = require('electron');
const { sampleCells, INK } = require('./lib/pixels');

const DRAW_LIMIT_MS = 60000;
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

// Two animation frames in the page, so a change of size has reached the screen.
const TWO_FRAMES = 'new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))';

/**
 * Make the window as tall as the page, so the capture shows the whole page
 * down to the summary. Only the height changes, so nothing moves sideways
 * and the cells of the report keep their places.
 */
async function fitPage(win) {
  const pageHeight = await win.webContents.executeJavaScript('Math.ceil(document.documentElement.scrollHeight)');
  const [width, height] = win.getContentSize();
  if (pageHeight > height) {
    win.setContentSize(width, pageHeight);
  }
  await win.webContents.executeJavaScript(TWO_FRAMES);
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

/** The colour of the tremor blocks in the report's theme. */
function tremorColour(report) {
  return INK[report.theme] ?? INK.light;
}

function checkTremorCells(win, image, scaleFactor, cells, colour) {
  const { width, height } = image.getSize(scaleFactor);
  const scale = width / win.getContentSize()[0];
  return sampleCells(image.toBitmap({ scaleFactor }), width, height, scale, cells, colour);
}

function jsonPath(pngPath) {
  return pngPath.endsWith('.png') ? `${pngPath.slice(0, -4)}.json` : `${pngPath}.json`;
}

function writeJson(pngPath, result) {
  fs.writeFileSync(jsonPath(pngPath), `${JSON.stringify(result, null, 2)}\n`);
}

/** @typedef {{message: object, loadMs: number, recording?: object}} Opened */

/**
 * Run one capture and return the exit code. open() sends the page what to
 * show. With --record-for it records first and also gives the recording's
 * file, exit code, signal, and status text.
 *
 * @param {{win: object, args: {file: string | null, capture: string}, open: () => Opened | Promise<Opened>, isOwnPage: (event: object) => boolean}} run
 * @returns {Promise<number>}
 */
async function runCapture({ win, args, open, isOwnPage }) {
  const drawn = waitForDrawn(isOwnPage);
  const started = performance.now();
  const { message, loadMs, recording = null } = await open();
  const file = recording === null ? args.file : recording.file;
  const report = await withLimit(drawn, DRAW_LIMIT_MS);
  if (report === null) {
    const text = `Nothing was drawn within ${DRAW_LIMIT_MS / 1000} seconds.`;
    console.error(text);
    writeJson(args.capture, { file, exitCode: 2, message: text, loadMs, recording });
    return 2;
  }
  const totalMs = performance.now() - started;
  await fitPage(win);
  const { image, scaleFactor, shownWindow } = await grab(win);
  fs.writeFileSync(args.capture, image.toPNG({ scaleFactor }));
  const [pageHasRequire, pageHasProcess] = await win.webContents.executeJavaScript(
    "[typeof require !== 'undefined', typeof process !== 'undefined']",
  );
  const recordingFailed = recording !== null && recording.exitCode !== 0;
  const exitCode = message.ok && !recordingFailed ? 0 : 1;
  const failure = !message.ok ? message.message : recordingFailed ? recording.text : null;
  if (failure !== null) {
    console.error(failure);
  }
  const colour = tremorColour(report);
  writeJson(args.capture, {
    file,
    exitCode,
    message: failure,
    recording,
    report,
    loadMs,
    drawMs: report.drawMs ?? null,
    totalMs,
    shownWindow,
    webPreferences: win.webContents.getLastWebPreferences(),
    pageHasRequire,
    pageHasProcess,
    theme: report.theme ?? null,
    tremorColour: colour,
    tremorCellPixels: message.ok ? checkTremorCells(win, image, scaleFactor, report.tremorCells, colour) : null,
  });
  return exitCode;
}

module.exports = { runCapture };
