'use strict';

const path = require('node:path');
const { RecordingError } = require('./errors');
const { readRecordPatterns } = require('./format');
const { readRecordingLines } = require('./read_text');
const { parseLines } = require('./parse');
const { buildTimeline } = require('./timeline');
const { placeWindows, tremorSpans } = require('./windows');
const { startText } = require('./title');

// Result codes 0 to 4 of core/window.h.
const CODE_COUNT = 5;

function showBoot(boot) {
  const timeline = buildTimeline(boot);
  const { placed, notPlaced, faults } = placeWindows(boot, timeline.stretches);
  const windowsByCode = new Array(CODE_COUNT).fill(0);
  for (const w of placed) {
    windowsByCode[w.code]++;
  }
  return {
    id: boot.id,
    firmware: boot.firmware,
    resetCause: boot.resetCause,
    stretches: timeline.stretches,
    timeS: timeline.timeS,
    gx: timeline.gx,
    gy: timeline.gy,
    gz: timeline.gz,
    breaks: timeline.breaks,
    windows: placed,
    tremorSpans: tremorSpans(placed),
    counts: {
      readings: timeline.timeS.length,
      windowsByCode,
      faults,
      notPlaced,
      noStretchReadings: timeline.noStretchReadings,
    },
  };
}

/**
 * Read, parse, and place a saved recording. The result holds only values that
 * structured clone can copy, so it can go to the page as it is.
 *
 * @param {string} filePath The recording.
 * @param {{docPath?: string, maxBytes?: number}} [options] The format document and the most text to read.
 * @returns {{file: string, fileName: string, startText: string | null, cutShort: boolean, counts: object, boots: object[]}}
 */
function loadRecording(filePath, { docPath, maxBytes } = {}) {
  const patterns = readRecordPatterns(docPath);
  const { lines, cutShort } = readRecordingLines(filePath, { maxBytes });
  const { boots, counts } = parseLines(lines, patterns);
  const fileName = path.basename(filePath);
  if (boots.length === 0) {
    throw new RecordingError(`${fileName} holds no B line in its ${counts.lines} lines, so it is not a recording from the watch.`);
  }
  const shown = boots.map(showBoot);
  if (shown.every((b) => b.counts.readings === 0)) {
    throw new RecordingError(`${fileName} holds no gyroscope reading that the viewer can place in time.`);
  }
  return { file: filePath, fileName, startText: startText(fileName, lines), cutShort, counts, boots: shown };
}

module.exports = { loadRecording };
