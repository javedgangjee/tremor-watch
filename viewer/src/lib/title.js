'use strict';

// The start of a recording as words, such as "Oct 28, 2026 at 14:28", for
// the title of the page. It comes from the file name that the Record button
// gives, or else from the CLOCK command that watch_cli.py record writes after
// the first B line.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// The names of recordingName() and freeRecordingPath() in recorder.js.
const FILE_NAME = /^tremor-(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})(?:-\d+)?\.txt\.gz$/;

// The ranges of CLOCK in the commands table of core/recording_format.md. The
// time lies from 1 January 2020 to before 1 January 2100, in microseconds
// since 1970, and the offset from -720 to 840 minutes.
const CLOCK_MIN_US = 1577836800000000;
const CLOCK_END_US = 4102444800000000;
const OFFSET_MIN = -720;
const OFFSET_MAX = 840;
const CLOCK_LINE = /^> CLOCK,(-?\d+),(-?\d+)$/;

function daysIn(year, month) {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/**
 * Give the date and time in a file name of the form
 * tremor-YYYY-MM-DD-HHMMSS.txt.gz or tremor-YYYY-MM-DD-HHMMSS-N.txt.gz, or
 * null when the name has another form or its date or time is not valid.
 *
 * @param {string} name
 * @returns {{year: number, month: number, day: number, hour: number, minute: number} | null}
 */
function dateFromFileName(name) {
  const found = FILE_NAME.exec(name);
  if (found === null) {
    return null;
  }
  const [year, month, day, hour, minute, second] = found.slice(1).map(Number);
  if (month < 1 || month > 12 || day < 1 || day > daysIn(year, month)) {
    return null;
  }
  if (hour > 23 || minute > 59 || second > 59) {
    return null;
  }
  return { year, month, day, hour, minute };
}

/**
 * Give the local date and time of the CLOCK command in the first line that
 * starts with "> " after the first B line, or null when that line is not a
 * CLOCK command within its ranges. The local time is the UTC time plus the
 * offset, read with UTC fields, so the laptop's own time zone does not change it.
 *
 * @param {string[]} lines The lines with no laptop time.
 * @returns {{year: number, month: number, day: number, hour: number, minute: number} | null}
 */
function dateFromClockLines(lines) {
  const b = lines.findIndex((line) => line.startsWith('B,'));
  if (b < 0) {
    return null;
  }
  let command = null;
  for (let i = b + 1; i < lines.length; i++) {
    if (lines[i].startsWith('> ')) {
      command = lines[i];
      break;
    }
  }
  const found = command === null ? null : CLOCK_LINE.exec(command);
  if (found === null) {
    return null;
  }
  const utcUs = Number(found[1]);
  const offset = Number(found[2]);
  if (!Number.isSafeInteger(utcUs) || utcUs < CLOCK_MIN_US || utcUs >= CLOCK_END_US) {
    return null;
  }
  if (offset < OFFSET_MIN || offset > OFFSET_MAX) {
    return null;
  }
  const local = new Date(Math.floor(utcUs / 1000) + offset * 60000);
  return {
    year: local.getUTCFullYear(),
    month: local.getUTCMonth() + 1,
    day: local.getUTCDate(),
    hour: local.getUTCHours(),
    minute: local.getUTCMinutes(),
  };
}

/**
 * Give a date and time as words, such as "Jan 5, 2027 at 09:05".
 *
 * @param {{year: number, month: number, day: number, hour: number, minute: number}} fields
 * @returns {string}
 */
function formatStart({ year, month, day, hour, minute }) {
  const two = (n) => String(n).padStart(2, '0');
  return `${MONTHS[month - 1]} ${day}, ${year} at ${two(hour)}:${two(minute)}`;
}

/**
 * Give the start of a recording as words, or null when neither its file name
 * nor its CLOCK line gives it.
 *
 * @param {string} fileName
 * @param {string[]} lines The lines with no laptop time.
 * @returns {string | null}
 */
function startText(fileName, lines) {
  const fields = dateFromFileName(fileName) ?? dateFromClockLines(lines);
  return fields === null ? null : formatStart(fields);
}

module.exports = { dateFromFileName, dateFromClockLines, formatStart, startText };
