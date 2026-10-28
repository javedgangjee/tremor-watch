'use strict';

// The rules of replay in core/replay.c and of tools/compare_session.py, with
// the extra checks of requirement 16 of feature 12.

const BURST_MAX = 256;
const COUNT_MIN = -32768;
const COUNT_MAX = 32767;

// The groups of each pattern that hold a whole number. An empty group, such as
// the window of a sensor fault answer, is allowed.
const WHOLE_GROUPS = {
  A: [0, 1],
  B: [0, 1, 2],
  D: [0, 1],
  F: [0, 1],
  R: [0, 1, 2, 3, 4, 5, 6],
  S: [0, 1, 2, 3, 4],
  T: [0, 1, 2],
  W: [0, 1, 2],
};

function isNumberText(text) {
  return text !== '' && Number.isFinite(Number(text));
}

/**
 * Match a record line to its pattern and turn its whole numbers into numbers.
 * Gives null when the line breaks its pattern or a number is not a safe integer.
 */
function readGroups(line, pattern, wholeGroups) {
  const found = pattern.exec(line);
  if (found === null) {
    return null;
  }
  const groups = found.slice(1);
  for (const i of wholeGroups) {
    if (groups[i] === '') {
      continue;
    }
    const value = Number(groups[i]);
    if (!Number.isSafeInteger(value)) {
      return null;
    }
    groups[i] = value;
  }
  return groups;
}

/** Turn the groups of each record line into a record, or null for a bad line. */
const READERS = {
  B: ([id, resetCause, firmware, tableHash]) => ({ id, resetCause, firmware, tableHash }),
  S: ([number, first, t0Us, rateUhz]) => ({ number, first, t0Us, rateUhz }),
  T: ([first, count, stampUs]) => (count >= 1 && count <= BURST_MAX ? { first, count, stampUs } : null),
  R: ([number, ...counts]) => (counts.every((c) => c >= COUNT_MIN && c <= COUNT_MAX) ? { number, gyro: counts.slice(0, 3) } : null),
  W: ([stretch, window, code, ...numbers]) => {
    if (window === '') {
      return { stretch, fault: true };
    }
    return numbers.every(isNumberText) ? { stretch, window, code, fault: false } : null;
  },
  F: () => ({}),
  D: () => ({}),
  A: () => ({}),
};

function newBoot({ id, resetCause, firmware, tableHash }) {
  return { id, resetCause, firmware, tableHash, sLines: new Map(), bursts: [], windows: new Map(), faults: 0 };
}

/**
 * Read the lines of a recording into boots, with the skip rules of replay.
 *
 * Each boot holds its last S line of each stretch number, its kept bursts with
 * their gyroscope counts, its windows keyed "stretch,window" with the last W
 * line holding, and its number of sensor fault answers.
 *
 * @param {string[]} lines The lines with no laptop time.
 * @param {Record<string, RegExp>} patterns The patterns from readRecordPatterns().
 * @returns {{boots: object[], counts: {lines: number, bad: number, droppedBursts: number}}}
 */
function parseLines(lines, patterns) {
  const counts = { lines: lines.length, bad: 0, droppedBursts: 0 };
  const boots = [];
  let boot = null;
  let held = null;

  // A burst counts only when it holds exactly its count of R lines in order.
  // At the end of the lines a burst that is in order but short is left out
  // without a count, because the capture stopped in it.
  function closeHeld(atEnd) {
    if (held === null) {
      return;
    }
    const { burst, got, broken } = held;
    held = null;
    if (!broken && got === burst.count) {
      boot.bursts.push(burst);
    } else if (broken || !atEnd) {
      counts.droppedBursts++;
    }
  }

  for (const line of lines) {
    const letter = line.length >= 2 && line[1] === ',' ? line[0] : '';
    if (!(letter in READERS) || (boot === null && letter !== 'B')) {
      continue;
    }
    const groups = readGroups(line, patterns[letter], WHOLE_GROUPS[letter]);
    const record = groups && READERS[letter](groups);
    if (!record) {
      // A broken B line counts as bad only after the first B line.
      if (boot !== null) {
        counts.bad++;
      }
      continue;
    }
    switch (letter) {
      case 'B':
        if (boot !== null) {
          closeHeld(false);
        }
        if (boot === null || record.id !== boot.id) {
          boot = newBoot(record);
          boots.push(boot);
        }
        break;
      case 'S':
        boot.sLines.set(record.number, { first: record.first, t0Us: record.t0Us, rateUhz: record.rateUhz });
        break;
      case 'T':
        closeHeld(false);
        held = {
          burst: { first: record.first, count: record.count, stampUs: record.stampUs, gyro: new Int16Array(record.count * 3) },
          got: 0,
          broken: false,
        };
        break;
      case 'R':
        if (held === null || held.broken) {
          break;
        }
        if (held.got >= held.burst.count || record.number !== held.burst.first + held.got) {
          held.broken = true;
          break;
        }
        held.burst.gyro.set(record.gyro, held.got * 3);
        held.got++;
        break;
      case 'W':
        if (record.fault) {
          boot.faults++;
        } else {
          const { stretch, window, code } = record;
          boot.windows.set(`${stretch},${window}`, { stretch, window, code });
        }
        break;
      default:
        // The F, D, and A lines are checked against their patterns only.
        break;
    }
  }
  if (boot !== null) {
    closeHeld(true);
  }
  return { boots, counts };
}

module.exports = { parseLines, BURST_MAX };
