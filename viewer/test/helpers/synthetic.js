'use strict';

// Builds the made-up recordings of specs/features/12-recording-viewer/validation.md.
// No committed recording holds a tremor answer, so these give the viewer
// tremor windows and every awkward case of its reader. The text depends on
// nothing outside this file and core/detector_tables.h, so each run gives the
// same text.

const fs = require('node:fs');
const path = require('node:path');

const TABLES = path.join(__dirname, '..', '..', '..', 'core', 'detector_tables.h');
const HASH = /#define DET_MODEL_SHA256 "([0-9a-f]{64})"/.exec(fs.readFileSync(TABLES, 'utf8'))[1];

const BURST = 11;
const RATE_UHZ = 114330200;
const STRETCH_1_RATE_UHZ = 114331000;
const WINDOW_S = 4;
const ROM_LINE = 'ESP-ROM:esp32s3-20210327';

const BOOT_A = 305419896;
const BOOT_B = 4294967295;
const BOOT_A_T0_US = 250000;
const BOOT_B_T0_US = 300000;
/** The stamp of the burst whose first reading is first, in a stretch from f0 at t0Us. */
function burstStamp(first, f0, t0Us, rateUhz) {
  return t0Us + Math.floor(((first - f0) * 1e12) / rateUhz + 0.5);
}

/** The number of bursts from f0 whose first reading lies before limitS seconds. */
function burstsBefore(limitS, rateUhz) {
  return Math.ceil((limitS * rateUhz) / 1e6 / BURST);
}

const STRETCH_0_BURSTS = burstsBefore(120, RATE_UHZ);
const STRETCH_1_BURSTS = 416;
const BOOT_B_BURSTS = burstsBefore(8, RATE_UHZ);

// Stretch 1 starts 6 milliseconds after the end of the last burst of stretch 0.
const T1_US =
  burstStamp((STRETCH_0_BURSTS - 1) * BURST, 0, BOOT_A_T0_US, RATE_UHZ) +
  Math.floor((BURST * 1e12) / RATE_UHZ + 0.5) +
  6000;

/** The shake in degrees per second on one axis at t seconds since the stretch's t0. */
function shakeDps(shakes, axis, t) {
  let dps = 0;
  for (const s of shakes) {
    if (s.axis === axis && t >= s.fromS && t < s.toS) {
      dps += s.dps * Math.sin(2 * Math.PI * s.hz * t);
    }
  }
  return dps;
}

/** Window 0 warms up, a window inside a tremor shake is tremor, and one that touches a sway is arm moving. */
function windowCode(n, shakes) {
  if (n === 0) {
    return 3;
  }
  const end = n + WINDOW_S;
  if (shakes.some((s) => s.kind === 'tremor' && n >= s.fromS && end <= s.toS)) {
    return 0;
  }
  if (shakes.some((s) => s.kind === 'sway' && end > s.fromS && n < s.toS)) {
    return 2;
  }
  return 1;
}

function rLine(n, stretch) {
  const t = ((n - stretch.f0) * 1e6) / stretch.rateUhz;
  const gyro = [0, 1, 2].map(
    (axis) => Math.round(32 * shakeDps(stretch.shakes, axis, t)) + Math.round(10 * Math.sin(0.37 * n + axis)),
  );
  return `R,${n},${gyro.join(',')},0,0,4096`;
}

/** Collects lines with a laptop time in front that never falls. */
class Writer {
  constructor() {
    this.lines = [];
    this.clockS = 0;
  }

  at(seconds) {
    this.clockS = Math.max(this.clockS, seconds);
  }

  add(text) {
    this.lines.push(`${this.clockS.toFixed(3)}\t${text}`);
  }

  text() {
    return `${this.lines.join('\n')}\n`;
  }
}

/**
 * Write the bursts of one stretch with their W lines. The hooks change the
 * lines of single bursts: lost(b) leaves a burst and its W lines out,
 * before(b) and after(b, t) add lines around a burst, and rText(b, j, text)
 * changes or drops (with null) its R line j.
 */
function writeStretch(out, stretch, hooks = {}) {
  const { lost = () => false, before = () => {}, after = () => {}, rText = (b, j, text) => text } = hooks;
  let nextWindow = 0;
  for (let b = 0; b < stretch.bursts; b++) {
    const first = stretch.f0 + b * BURST;
    const t = ((first - stretch.f0) * 1e6) / stretch.rateUhz;
    const stamp = burstStamp(first, stretch.f0, stretch.t0Us, stretch.rateUhz);
    out.at(stretch.laptopS + stamp / 1e6);
    const due = [];
    while (stretch.windows && t >= nextWindow + WINDOW_S) {
      due.push(nextWindow++);
    }
    if (lost(b)) {
      continue;
    }
    before(b);
    out.add(`T,${first},${BURST},${stamp}`);
    for (let j = 0; j < BURST; j++) {
      const text = rText(b, j, rLine(first + j, stretch));
      if (text !== null) {
        out.add(text);
      }
    }
    for (const n of due) {
      out.add(`W,${stretch.number},${n},${windowCode(n, stretch.shakes)},0.5,10,5`);
    }
    after(b, t);
  }
}

/** Calls fn once, at the first burst at or after fromS seconds. */
function onceFrom(fromS, fn) {
  let done = false;
  return (b, t) => {
    if (!done && t >= fromS) {
      done = true;
      fn();
    }
  };
}

function bootA(out) {
  const bLine = `B,${BOOT_A},11,12,${HASH}`;
  const rateLine = `S,0,0,${BOOT_A_T0_US},${RATE_UHZ},1024`;
  const stretch0 = {
    number: 0,
    f0: 0,
    t0Us: BOOT_A_T0_US,
    rateUhz: RATE_UHZ,
    bursts: STRETCH_0_BURSTS,
    windows: true,
    laptopS: 1,
    shakes: [
      { axis: 0, dps: 100, hz: 5, fromS: 30, toS: 60, kind: 'tremor' },
      { axis: 1, dps: 60, hz: 0.5, fromS: 80, toS: 95, kind: 'sway' },
    ],
  };
  out.add(bLine);
  out.add('START uptime_us=1');
  out.add(`S,0,0,${BOOT_A_T0_US},0,1024`);
  const rateFrom10 = onceFrom(10, () => out.add(rateLine));
  const extrasFrom20 = onceFrom(20, () => {
    for (const text of ['> TONE,0', 'A,4,0', 'F,0,1', 'W,0,,4,,,', 'D,20000000,', 'TOUCH x=1 y=2']) {
      out.add(text);
    }
  });
  writeStretch(out, stretch0, {
    // Bursts 1040 to 1042 are lost, and the watch sends B and S again after them.
    lost: (b) => b >= 1040 && b <= 1042,
    before: (b) => {
      if (b === 1043) {
        out.add(bLine);
        out.add(rateLine);
      }
    },
    rText: (b, j, text) => (b === 728 && j === 2 ? 'R,1234,5' : text),
    after: (b, t) => {
      rateFrom10(b, t);
      extrasFrom20(b, t);
    },
  });

  const stretch1 = {
    number: 1,
    f0: STRETCH_0_BURSTS * BURST,
    t0Us: T1_US,
    rateUhz: STRETCH_1_RATE_UHZ,
    bursts: STRETCH_1_BURSTS,
    windows: true,
    laptopS: 1,
    shakes: [{ axis: 0, dps: 150, hz: 5.5, fromS: 10, toS: 25, kind: 'tremor' }],
  };
  out.add(`S,1,${stretch1.f0},${T1_US},${STRETCH_1_RATE_UHZ},1024`);
  writeStretch(out, stretch1);
}

function bootB(out) {
  out.add('> RESET');
  out.add(ROM_LINE);
  out.add(`B,${BOOT_B},1,12,${HASH}`);
  out.add(`S,0,0,${BOOT_B_T0_US},0,1024`);
  const stretch = {
    number: 0,
    f0: 0,
    t0Us: BOOT_B_T0_US,
    rateUhz: RATE_UHZ,
    bursts: BOOT_B_BURSTS,
    windows: false,
    laptopS: out.clockS + 1,
    shakes: [],
  };
  writeStretch(out, stretch, {
    after: (b) => {
      if (b === 10) {
        out.add('W,0,,4,,,');
      }
    },
    // The capture stops after 5 R lines of the last burst.
    rText: (b, j, text) => (b === BOOT_B_BURSTS - 1 && j >= 5 ? null : text),
  });
}

/**
 * Build the made-up recording of validation.md, which
 * viewer/test/fixtures/synthetic.txt.gz holds.
 *
 * @returns {string}
 */
function buildSyntheticText() {
  const out = new Writer();
  out.add(ROM_LINE);
  out.add('T,500,11,123');
  out.add('R,500,1,2,3,4,5,6');
  bootA(out);
  bootB(out);
  return out.text();
}

/**
 * Build a long recording of one boot and one stretch at RATE_UHZ, with a 5 Hz
 * shake of 100 degrees per second on the x axis for 20 seconds every 10
 * minutes from 300 seconds.
 *
 * @param {number} minutes The length of the recording.
 * @returns {string}
 */
function buildLongText(minutes) {
  const limitS = minutes * 60;
  const shakes = [];
  for (let fromS = 300; fromS < limitS; fromS += 600) {
    shakes.push({ axis: 0, dps: 100, hz: 5, fromS, toS: fromS + 20, kind: 'tremor' });
  }
  const out = new Writer();
  out.add(`B,${BOOT_A},11,12,${HASH}`);
  out.add(`S,0,0,${BOOT_A_T0_US},0,1024`);
  const rateFrom10 = onceFrom(10, () => out.add(`S,0,0,${BOOT_A_T0_US},${RATE_UHZ},1024`));
  const stretch = {
    number: 0,
    f0: 0,
    t0Us: BOOT_A_T0_US,
    rateUhz: RATE_UHZ,
    bursts: burstsBefore(limitS, RATE_UHZ),
    windows: true,
    laptopS: 1,
    shakes,
  };
  writeStretch(out, stretch, { after: rateFrom10 });
  return out.text();
}

module.exports = {
  buildSyntheticText,
  buildLongText,
  burstStamp,
  HASH,
  BOOT_A,
  BOOT_B,
  T1_US,
  RATE_UHZ,
  STRETCH_1_RATE_UHZ,
};
