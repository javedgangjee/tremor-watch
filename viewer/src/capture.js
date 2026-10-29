'use strict';

// Runs the viewer with no person: open FILE, or record for --record-for
// seconds and open the new file, wait until the page has drawn, save the
// window as a PNG with a JSON report beside it, and give the exit code. Exit
// code 0 means the file was drawn, 1 that it could not be read or the
// recording failed, and 2 that nothing was drawn within the limit.

const fs = require('node:fs');
const { performance } = require('node:perf_hooks');
const { ipcMain } = require('electron');
const { sampleCells, samplePoints, countColumn, INK, INK_SECONDARY } = require('./lib/pixels');

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
 * down to the bottom of the cards. Only the height changes, so nothing moves
 * sideways and the cells of the report keep their places.
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

/** The captured image as a bitmap, its size, and its image pixels per page pixel. */
function imageData(win, image, scaleFactor) {
  const { width, height } = image.getSize(scaleFactor);
  const scale = width / win.getContentSize()[0];
  return { bitmap: image.toBitmap({ scaleFactor }), width, height, scale };
}

function checkTremorCells(data, cells, colour) {
  return sampleCells(data.bitmap, data.width, data.height, data.scale, cells, colour);
}

// The shares of a tremor line's height at which its colour is checked.
const LINE_POINTS = [0.25, 0.5, 0.75];

/** Check three points down the middle of each tremor line of every chart. */
function checkTremorLines(data, report, colour) {
  const points = [];
  for (const lines of report.tremorLines ?? []) {
    for (const line of lines) {
      for (const share of LINE_POINTS) {
        points.push({ x: line.x + line.width / 2, y: line.top + line.height * share });
      }
    }
  }
  return samplePoints(data.bitmap, data.width, data.height, data.scale, points, colour);
}

/**
 * Count the pixels down each selection line of every chart that match
 * --ink-secondary and --ink of the theme.
 */
function checkSelectionLines(data, report) {
  const colours = [INK_SECONDARY[report.theme] ?? INK_SECONDARY.light, tremorColour(report)];
  const total = { lines: 0, sampled: 0, lineColour: 0, tremorColour: 0 };
  for (const lines of report.selectionLines ?? []) {
    for (const line of lines) {
      const { sampled, matches } = countColumn(data.bitmap, data.width, data.height, data.scale, line, colours);
      total.lines++;
      total.sampled += sampled;
      total.lineColour += matches[0];
      total.tremorColour += matches[1];
    }
  }
  return total;
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
  const data = message.ok ? imageData(win, image, scaleFactor) : null;
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
    tremorCellPixels: message.ok ? checkTremorCells(data, report.tremorCells, colour) : null,
    tremorLinePixels: message.ok ? checkTremorLines(data, report, colour) : null,
    selectionLinePixels: message.ok ? checkSelectionLines(data, report) : null,
  });
  return exitCode;
}

module.exports = { runCapture };
