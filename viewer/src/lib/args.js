'use strict';

const path = require('node:path');
const { ArgsError } = require('./errors');

const USAGE = 'npm --prefix viewer start -- [FILE] [--boot ID] [--capture OUT.png] [--record-for SECONDS]';
// The longest --record-for, one day.
const MAX_RECORD_S = 86400;

function optionValue(argv, i) {
  const value = argv[i + 1];
  if (value === undefined || value.startsWith('--')) {
    throw new ArgsError(`${argv[i]} needs a value.`);
  }
  return value;
}

function bootIdFrom(text) {
  const id = Number(text);
  if (!/^\d+$/.test(text) || !Number.isSafeInteger(id)) {
    throw new ArgsError(`The boot ID ${text} is not a whole number.`);
  }
  return id;
}

function recordSecondsFrom(text) {
  const seconds = Number(text);
  if (!/^\d+$/.test(text) || seconds < 1 || seconds > MAX_RECORD_S) {
    throw new ArgsError(`--record-for takes a whole number of seconds from 1 to ${MAX_RECORD_S}, not ${text}.`);
  }
  return seconds;
}

/**
 * Read the viewer's arguments. Relative paths resolve against cwd.
 *
 * @param {string[]} argv The arguments after Electron's own.
 * @param {string} cwd The folder the command ran from.
 * @returns {{file: string | null, capture: string | null, bootId: number | null, recordFor: number | null}}
 */
function parseArgs(argv, cwd) {
  const args = { file: null, capture: null, bootId: null, recordFor: null };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--capture') {
      args.capture = path.resolve(cwd, optionValue(argv, i));
      i++;
    } else if (arg === '--boot') {
      args.bootId = bootIdFrom(optionValue(argv, i));
      i++;
    } else if (arg === '--record-for') {
      args.recordFor = recordSecondsFrom(optionValue(argv, i));
      i++;
    } else if (arg.startsWith('-')) {
      throw new ArgsError(`${arg} is not an option.`);
    } else if (args.file !== null) {
      throw new ArgsError(`Give one FILE, not ${args.file} and ${arg}.`);
    } else {
      args.file = path.resolve(cwd, arg);
    }
  }
  if (args.recordFor !== null) {
    if (args.capture === null) {
      throw new ArgsError('--record-for needs --capture.');
    }
    if (args.file !== null) {
      throw new ArgsError('--record-for takes no FILE, because it opens the file it records.');
    }
  } else if (args.capture !== null && args.file === null) {
    throw new ArgsError('--capture needs a FILE.');
  }
  return args;
}

module.exports = { parseArgs, USAGE };
